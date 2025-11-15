import cv2
import numpy as np


# CONFIGURACIÓN VISUAL

COLOR_VEHICLE = (0, 255, 0)        
COLOR_PLATE = (255, 200, 0)        
COLOR_TEXT_BG = (0, 0, 0)        
COLOR_TEXT = (255, 255, 255)       

FONT = cv2.FONT_HERSHEY_SIMPLEX
THICKNESS_BOX = 2
THICKNESS_TEXT = 2
SCALE_TEXT = 0.6


# 
#  FUNCIÓN PRINCIPAL DE DIBUJO

def draw_detections(frame, results):
    """
    Dibuja rectángulos, texto y etiquetas de cada vehículo detectado.
    """
    if results is None or not isinstance(results, dict):
        return frame

    overlay = frame.copy()

    for track_id, data in results.items():
        x1 = y1 = x2 = y2 = None  # valores iniciales seguros

        
        # VEHÍCULO
        # 
        if "car" in data and "bbox" in data["car"]:
            x1, y1, x2, y2 = map(int, data["car"]["bbox"])
            cv2.rectangle(overlay, (x1, y1), (x2, y2), COLOR_VEHICLE, THICKNESS_BOX)

            tipo = data.get("tipo", "vehículo")
            icon = {
                "car": "🚗",
                "motorcycle": "🏍️",
                "bus": "🚌",
                "truck": "🚚"
            }.get(tipo, "🚘")

            label_vehicle = f"{icon} {tipo.upper()}"
            _draw_label(overlay, label_vehicle, (x1, max(15, y1 - 10)), COLOR_VEHICLE)

        
        # PLACA
        # 
        if "license_plate" in data:
            lp = data["license_plate"]
            if lp.get("bbox"):
                px1, py1, px2, py2 = map(int, lp["bbox"])
                cv2.rectangle(overlay, (px1, py1), (px2, py2), COLOR_PLATE, 2)

            text = lp.get("text", None)
            score = lp.get("text_score", 0.0)

            if text:
                # Si no se detectó el auto, usamos la posición de la placa para colocar texto
                pos_x = x1 if x1 is not None else px1
                pos_y = (y2 + 25) if y2 is not None else (py2 + 25)
                conf_str = f"{text} ({score*100:.0f}%)"
                _draw_label(overlay, conf_str, (pos_x, pos_y), COLOR_PLATE)

        #
        #  ID del vehículo
    
        if x1 is not None and y1 is not None:
            cv2.putText(
                overlay,
                f"ID:{track_id}",
                (x1 + 5, y1 + 15),
                FONT,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )

    frame = cv2.addWeighted(overlay, 0.9, frame, 0.1, 0)
    return frame


# 
#  FUNCIÓN AUXILIAR

def _draw_label(img, text, pos, color_box):
    """
    Dibuja una etiqueta con fondo negro y texto coloreado.
    """
    (text_w, text_h), _ = cv2.getTextSize(text, FONT, SCALE_TEXT, THICKNESS_TEXT)
    x, y = pos
    x = max(0, x)
    y = max(text_h + 5, y)

    cv2.rectangle(img, (x, y - text_h - 4), (x + text_w + 2, y), COLOR_TEXT_BG, -1)
    cv2.putText(
        img,
        text,
        (x + 1, y - 2),
        FONT,
        SCALE_TEXT,
        color_box,
        THICKNESS_TEXT,
        cv2.LINE_AA
    )
