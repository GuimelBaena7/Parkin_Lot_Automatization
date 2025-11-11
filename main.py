# main.py
from ultralytics import YOLO
import cv2
import numpy as np
import os
import sqlite3
from datetime import datetime
from collections import defaultdict, deque
from util import (
    read_license_plate,
    license_complies_format,
    seleccionar_mas_cercano,
    consolidar_buffer,
    infer_direction_from_history,
)
from visualize import draw_detections
from sort.sort import Sort

# =====================================
# 🔧 CONFIGURACIÓN GLOBAL
# =====================================
DB_PATH = "estacionamiento.db"
OUTPUT_VIDEO = "salida_detectada.mp4"
UNIQUE_FOLDER = "detecciones_unicas"
os.makedirs(UNIQUE_FOLDER, exist_ok=True)

VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
MIN_PLATE_LEN = 3
FPS_DEFAULT = 20
MIN_FRAMES_BUFFER = 7       # mínimo lecturas válidas antes de intentar consolidar
PLATE_CONFIRM_THRESHOLD = 0.50  # confianza mínima final para aceptar una placa
STRICT_MODE = True           # no cambia de vehículo hasta lectura confiable
DIRECTION_SIGN = 1           # +1 si cámara abajo, -1 si está invertida

# =====================================
# 🔍 INICIALIZACIÓN DE MODELOS Y DB
# =====================================
coco_model = YOLO("yolo11n.pt")
lp_model = YOLO("license_plate_detector.pt")
mot_tracker = Sort()

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Crear tabla principal si no existe
cursor.execute('''
CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_vehiculo TEXT,
    placa_final TEXT,
    hora_entrada TEXT,
    direccion TEXT,
    url_imagen TEXT,
    id_sort_original INTEGER,
    frames_hasta_placa INTEGER
)
''')
conn.commit()

# =====================================
# 🧠 ESTRUCTURAS EN MEMORIA
# =====================================
vehiculo_activo_id = None
vehiculo_estado = {}            # sort_id -> {bbox, frame_inicial, tipo, ...}
movement_history = defaultdict(lambda: deque(maxlen=30))  # para inferir dirección
lecturas_ocr = defaultdict(list)  # sort_id -> [(texto, score, frame_number)]

# =====================================
# 🧩 FUNCIÓN PRINCIPAL
# =====================================
def main():
    global vehiculo_activo_id, vehiculo_estado, lecturas_ocr, movement_history

    video_path = input("Ingresa la ruta del video o '0' para cámara en vivo: ").strip()
    cap = cv2.VideoCapture(0 if video_path == '0' else video_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or FPS_DEFAULT
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

    out = cv2.VideoWriter(OUTPUT_VIDEO, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    print(f"\n🎥 Framerate detectado: {fps} fps")

    frame_nmr = 0
    print("🚗 Iniciando detección... presiona 'q' para salir.\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Fin de video o cámara.")
                break

            frame_nmr += 1
            raw_detections = coco_model(frame)[0]

            # Filtramos detecciones de vehículos
            dets = [
                [x1, y1, x2, y2, score, VEHICLE_CLASSES[int(cls)]]
                for x1, y1, x2, y2, score, cls in raw_detections.boxes.data.tolist()
                if int(cls) in VEHICLE_CLASSES
            ]

            # Seguimiento con SORT
            tracks = mot_tracker.update(
                np.array([d[:5] for d in dets], dtype=np.float32) if dets else np.empty((0, 5))
            )
            best_track = seleccionar_mas_cercano(tracks)

            # Si no hay vehículo activo y se detecta uno nuevo
            if vehiculo_activo_id is None and best_track is not None:
                vehiculo_activo_id = int(best_track[4])
                vehiculo_estado[vehiculo_activo_id] = {
                    "bbox": best_track[:4],
                    "tipo": "desconocido",
                    "frame_inicial": frame_nmr,
                }
                lecturas_ocr[vehiculo_activo_id] = []
                print(f"🆕 Nuevo vehículo activo: {vehiculo_activo_id} en frame {frame_nmr}")

            # Si hay un vehículo activo, procesarlo
            if vehiculo_activo_id is not None and vehiculo_activo_id in vehiculo_estado:
                tx1, ty1, tx2, ty2 = vehiculo_estado[vehiculo_activo_id]["bbox"]
                tx1, ty1, tx2, ty2 = map(int, [tx1, ty1, tx2, ty2])
                h, w, _ = frame.shape

                # Verificar límites válidos
                if tx1 < 0 or ty1 < 0 or tx2 > w or ty2 > h or tx1 >= tx2 or ty1 >= ty2:
                    continue  # Omitir detección inválida

                car_crop = frame[ty1:ty2, tx1:tx2]

                # Evitar recortes vacíos o corruptos
                if car_crop is None or car_crop.size == 0:
                    continue

                plates = lp_model(car_crop)[0]

                # Detectar placas dentro del vehículo
                plates = lp_model(car_crop)[0]
                if plates.boxes is not None:
                    for p in plates.boxes.data.tolist():
                        x1, y1, x2, y2, score, _ = p
                        license_crop = car_crop[int(y1):int(y2), int(x1):int(x2)]
                        placa_read, conf_read = read_license_plate(license_crop)
                        if placa_read and len(placa_read) >= MIN_PLATE_LEN:
                            lecturas_ocr[vehiculo_activo_id].append((placa_read, conf_read, frame_nmr))
                            # Feedback de lectura
                            print(f"📖 OCR[{vehiculo_activo_id}] -> {placa_read} ({conf_read:.2f})")

                # Consolidar cuando haya suficientes lecturas
                num_lecturas = len(lecturas_ocr[vehiculo_activo_id])
                if num_lecturas >= MIN_FRAMES_BUFFER:
                    lecturas_validas = [(t, s) for t, s, _ in lecturas_ocr[vehiculo_activo_id]]
                    best_placa, best_conf = consolidar_buffer(lecturas_validas)
                    direction = infer_direction_from_history(movement_history[vehiculo_activo_id])

                    if best_placa and license_complies_format(best_placa) and best_conf >= PLATE_CONFIRM_THRESHOLD:
                        hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        frames_usados = frame_nmr - vehiculo_estado[vehiculo_activo_id]["frame_inicial"]
                        filepath = os.path.join(
                            UNIQUE_FOLDER, f"{best_placa}_{vehiculo_activo_id}_{frame_nmr}.jpg"
                        )
                        cv2.imwrite(filepath, frame)

                        conn.execute(
                            """
                            INSERT INTO registros
                            (tipo_vehiculo, placa_final, hora_entrada, direccion, url_imagen, id_sort_original, frames_hasta_placa)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            ("car", best_placa, hora_actual, direction, filepath, vehiculo_activo_id, frames_usados),
                        )
                        conn.commit()

                        print(
                            f"✅ Vehículo consolidado ID={vehiculo_activo_id} "
                            f"placa={best_placa} conf={best_conf:.2f} frames={frames_usados}"
                        )

                        # Limpiar estado del vehículo
                        movement_history.pop(vehiculo_activo_id, None)
                        lecturas_ocr.pop(vehiculo_activo_id, None)
                        vehiculo_estado.pop(vehiculo_activo_id, None)
                        vehiculo_activo_id = None

            # Dibujar visualización
            frame_vis = frame.copy()
            if vehiculo_activo_id is not None and vehiculo_activo_id in vehiculo_estado:
                draw_detections(
                    frame_vis,
                    {
                        vehiculo_activo_id: {
                            "car": {"bbox": vehiculo_estado[vehiculo_activo_id]["bbox"]},
                            "license_plate": {
                                "bbox": (0, 0, 0, 0),
                                "text": "...",
                                "text_score": 0.0,
                            },
                        }
                    },
                )

            out.write(frame_vis)

    finally:
        cap.release()
        out.release()
        conn.commit()
        conn.close()
        cv2.destroyAllWindows()
        print(f"\n📁 Video guardado en: {OUTPUT_VIDEO}")


# =====================================
# 🚀 EJECUCIÓN
# =====================================
if __name__ == "__main__":
    main()
