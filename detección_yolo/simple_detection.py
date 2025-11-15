import cv2
import numpy as np
from datetime import datetime
import os
import sqlite3
import re

# Configuración simple sin dependencias externas complejas
DB_PATH = "detecciones.db"
OUTPUT_FOLDER = "detecciones_guardadas"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Inicializar base de datos
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS detecciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        placa TEXT,
        timestamp TEXT,
        imagen_path TEXT,
        confianza REAL
    )
    ''')
    conn.commit()
    return conn

# Simulador de detección YOLO (para desarrollo sin modelo)
def detectar_vehiculos_simple(frame):
    """Simulador de detección de vehículos"""
    height, width = frame.shape[:2]
    
    # Simular detección en el centro del frame
    detections = []
    
    # Área central donde "detectamos" vehículos
    center_x, center_y = width // 2, height // 2
    box_w, box_h = width // 3, height // 3
    
    x1 = center_x - box_w // 2
    y1 = center_y - box_h // 2
    x2 = center_x + box_w // 2
    y2 = center_y + box_h // 2
    
    detections.append({
        'bbox': (x1, y1, x2, y2),
        'confidence': 0.85,
        'class': 'car'
    })
    
    return detections

def detectar_placa_simple(roi):
    """Simulador de OCR para placas"""
    # Generar placa aleatoria para demostración
    import random
    letras = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
    numeros = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
    
    # Formato colombiano: ABC123 o ABC12D
    placa = ''.join(random.choices(letras, k=3)) + ''.join(random.choices(numeros, k=3))
    confianza = random.uniform(0.7, 0.95)
    
    return placa, confianza

def validar_placa_colombiana(placa):
    """Validar formato de placa colombiana"""
    if not placa or len(placa) < 6:
        return False
    
    # Patrones comunes colombianos
    patrones = [
        r'^[A-Z]{3}[0-9]{3}$',  # ABC123
        r'^[A-Z]{3}[0-9]{2}[A-Z]$',  # ABC12D
        r'^[A-Z]{2}[0-9]{4}$',  # AB1234
    ]
    
    return any(re.match(patron, placa.upper()) for patron in patrones)

def procesar_frame_simple(frame, frame_count=0):
    """Procesar frame con detección simple"""
    frame_result = frame.copy()
    
    try:
        # Detectar vehículos
        vehiculos = detectar_vehiculos_simple(frame)
        
        for vehiculo in vehiculos:
            x1, y1, x2, y2 = vehiculo['bbox']
            
            # Dibujar bounding box del vehículo
            cv2.rectangle(frame_result, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame_result, f"Vehiculo {vehiculo['confidence']:.2f}", 
                       (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Extraer ROI para placa
            roi = frame[y1:y2, x1:x2]
            if roi.size > 0:
                placa, confianza = detectar_placa_simple(roi)
                
                if validar_placa_colombiana(placa) and confianza > 0.8:
                    # Dibujar información de la placa
                    cv2.rectangle(frame_result, (x1, y2-40), (x2, y2), (255, 0, 0), -1)
                    cv2.putText(frame_result, f"PLACA: {placa}", 
                               (x1+5, y2-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(frame_result, f"Conf: {confianza:.2f}", 
                               (x1+5, y2-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    
                    # Guardar detección cada 30 frames (evitar spam)
                    if frame_count % 30 == 0:
                        guardar_deteccion(frame_result, placa, confianza)
        
        # Agregar información del frame
        cv2.putText(frame_result, f"Frame: {frame_count}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame_result, f"Detecciones: {len(vehiculos)}", 
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
    except Exception as e:
        print(f"Error en procesamiento: {e}")
        cv2.putText(frame_result, f"Error: {str(e)[:50]}", 
                   (10, frame.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    return frame_result

def guardar_deteccion(frame, placa, confianza):
    """Guardar detección en base de datos y archivo"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{placa}_{timestamp}.jpg"
        filepath = os.path.join(OUTPUT_FOLDER, filename)
        
        # Guardar imagen
        cv2.imwrite(filepath, frame)
        
        # Guardar en base de datos
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO detecciones (placa, timestamp, imagen_path, confianza) VALUES (?, ?, ?, ?)",
            (placa, datetime.now().isoformat(), filepath, confianza)
        )
        conn.commit()
        conn.close()
        
        print(f"✅ Detección guardada: {placa} ({confianza:.2f})")
        
    except Exception as e:
        print(f"❌ Error guardando detección: {e}")

# Función principal para usar desde el backend
def detectar_frame(frame, frame_nmr):
    """Función principal llamada desde el backend"""
    return procesar_frame_simple(frame, frame_nmr)

# Inicializar DB al importar
init_db()