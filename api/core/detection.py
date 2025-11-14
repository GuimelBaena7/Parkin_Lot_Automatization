# api/core/detection.py
"""
Wrapper para detección con integración de facturación automática
"""
import cv2
import numpy as np
from datetime import datetime
import os

try:
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from main import detectar_frame as detectar_frame_main
except Exception:
    detectar_frame_main = None

def procesar_frame(frame, frame_nmr=0, camara_id=None, db=None):
    """
    Procesa frame con detección YOLO + OCR y crea facturas automáticamente
    """
    if detectar_frame_main:
        try:
            frame_procesado = detectar_frame_main(frame, frame_nmr)
            return frame_procesado
        except Exception as e:
            print("Error en detectar_frame:", e)
            return frame
    else:
        frame_copy = frame.copy()
        cv2.putText(frame_copy, f"Camara {camara_id} - Frame {frame_nmr}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return frame_copy

def crear_registro_con_factura(db, camara_id: int, placa: str, tipo_vehiculo: str = "car"):
    """
    Crea registro de detección y factura automáticamente
    """
    from ..crud import crear_registro, crear_factura
    
    try:
        registro = crear_registro(
            db=db,
            camara_id=camara_id,
            tipo_vehiculo=tipo_vehiculo,
            placa_final=placa,
            confianza=0.8,
            direccion="entrada",
            ruta_imagen=None
        )
        
        if registro:
            factura = crear_factura(db, registro.id)
            return registro, factura
        
    except Exception as e:
        return None, None
    
    return None, None

