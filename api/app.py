"""
FastAPI Backend para Sistema de Detección de Placas con Múltiples Cámaras

Funcionalidades:
- API REST para administrar cámaras dinámicamente
- WebSockets independientes por cámara (/ws/camara/{cam_id})
- Procesamiento YOLO + OCR en tiempo real
- Base de datos SQLite con SQLAlchemy
- Guardado de imágenes detectadas en /static/detecciones
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import asyncio
import logging
from .database import SessionLocal, engine, UNIQUE_FOLDER_PATH
from .models import Base
from .schemas import CamaraCreate, CamaraResponse, RegistroResponse
from .crud import (crear_camara, obtener_camaras, eliminar_camara, obtener_registros, 
                   obtener_registro_por_id, crear_factura, obtener_facturas_activas, 
                   cerrar_factura, obtener_factura_por_registro, calcular_valor_factura)
from .core.camera_manager import CameraManager
import os
os.makedirs("static", exist_ok=True)

# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sistema de Detección de Placas",
    description="Backend para múltiples cámaras con YOLO + OCR",
    version="1.0.0"
)

# Configurar CORS para permitir conexiones desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos (imágenes detectadas)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Instancia global del administrador de cámaras
camera_manager = CameraManager()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    """Dependencia para obtener sesión de base de datos"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== ENDPOINTS REST ====================

@app.post("/camaras", response_model=CamaraResponse)
async def registrar_camara(camara: CamaraCreate, db: Session = Depends(get_db)):
    """
    Registra una nueva cámara en el sistema
    
    El frontend envía:
    {
        "nombre": "Camara Entrada",
        "url": "rtsp://mi-camara" 
    }
    """
    try:
        nueva_camara = crear_camara(db, camara)
        logger.info(f"Cámara registrada: {nueva_camara.nombre} (ID: {nueva_camara.id})")
        return nueva_camara
    except Exception as e:
        logger.error(f"Error registrando cámara: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/camaras", response_model=list[CamaraResponse])
async def listar_camaras(db: Session = Depends(get_db)):
    """Lista todas las cámaras registradas"""
    return obtener_camaras(db)

@app.delete("/camaras/{camara_id}")
async def eliminar_camara_endpoint(camara_id: int, db: Session = Depends(get_db)):
    """
    Elimina una cámara del sistema
    También detiene su WebSocket si está activo
    """
    try:
        # Detener WebSocket si está activo
        await camera_manager.stop_camera(camara_id)
        
        # Eliminar de base de datos
        if eliminar_camara(db, camara_id):
            logger.info(f"Cámara {camara_id} eliminada")
            return {"message": "Cámara eliminada exitosamente"}
        else:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
    except Exception as e:
        logger.error(f"Error eliminando cámara {camara_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/registros", response_model=list[RegistroResponse])
async def listar_registros(db: Session = Depends(get_db)):
    """Lista todos los registros de detecciones"""
    return obtener_registros(db)

@app.get("/registros/{registro_id}/imagen")
async def ver_imagen_detectada(registro_id: int, db: Session = Depends(get_db)):
    """
    Devuelve la imagen de una detección específica
    Ruta: /registros/{id}/imagen
    """
    registro = obtener_registro_por_id(db, registro_id)
    if not registro or not registro.ruta_imagen:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    
    return FileResponse(registro.ruta_imagen)

# ==================== WEBSOCKETS DINÁMICOS ====================

@app.websocket("/ws/camara/{cam_id}")
async def websocket_camara(websocket: WebSocket, cam_id: int, db: Session = Depends(get_db)):
    """
    WebSocket dinámico por cámara
    
    Funcionamiento:
    1. El frontend se conecta a /ws/camara/{cam_id}
    2. Se obtiene la URL de la cámara desde la base de datos
    3. Se inicia el procesamiento YOLO + OCR
    4. Se envían frames procesados en base64 al cliente
    """
    await websocket.accept()
    logger.info(f"Cliente conectado a cámara {cam_id}")
    
    try:
        # Obtener información de la cámara
        camaras = obtener_camaras(db)
        camara = next((c for c in camaras if c.id == cam_id), None)
        
        if not camara:
            await websocket.send_text("ERROR: Cámara no encontrada")
            await websocket.close()
            return
        
        # Iniciar procesamiento de la cámara
        await camera_manager.start_camera(cam_id, camara.url, websocket, db)
        
        # Mantener conexión activa
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                await asyncio.sleep(0.1)
        
    except WebSocketDisconnect:
        logger.info(f"Cliente desconectado de cámara {cam_id}")
    except Exception as e:
        logger.error(f"Error en WebSocket cámara {cam_id}: {e}")
    finally:
        await camera_manager.unregister_listener(cam_id, websocket)

# ==================== ENDPOINTS DE FACTURACIÓN ====================

@app.get("/api/camaras", response_model=list[CamaraResponse])
async def get_camaras_frontend(db: Session = Depends(get_db)):
    """Endpoint compatible con frontend - Lista cámaras"""
    return obtener_camaras(db)

@app.post("/api/camaras", response_model=CamaraResponse)
async def create_camara_frontend(camara: CamaraCreate, db: Session = Depends(get_db)):
    """Endpoint compatible con frontend - Crear cámara"""
    return crear_camara(db, camara)

@app.delete("/api/camaras/{camara_id}")
async def delete_camara_frontend(camara_id: int, db: Session = Depends(get_db)):
    """Endpoint compatible con frontend - Eliminar cámara"""
    await camera_manager.stop_camera(camara_id)
    if eliminar_camara(db, camara_id):
        return {"message": "Cámara eliminada"}
    raise HTTPException(status_code=404, detail="Cámara no encontrada")

@app.get("/api/registros")
async def get_registros_frontend(estado: str = None, db: Session = Depends(get_db)):
    """Endpoint compatible con frontend - Lista registros con facturas"""
    from .crud import obtener_facturas_activas, obtener_factura_por_registro, calcular_valor_factura
    
    if estado == "activo":
        # Solo vehículos activos (con facturas abiertas)
        facturas_activas = obtener_facturas_activas(db)
        result = []
        
        for factura in facturas_activas:
            registro = factura.registro
            valor_actual, horas = calcular_valor_factura(factura.hora_entrada)
            
            result.append({
                "id": registro.id,
                "placa": registro.placa_final,
                "hora_entrada": factura.hora_entrada.isoformat(),
                "hora_salida": None,
                "estado": "activo",
                "camara_id": registro.camara_id,
                "tipo_vehiculo": registro.tipo_vehiculo,
                "url_imagen": f"/registros/{registro.id}/imagen" if registro.ruta_imagen else None,
                "valor_actual": valor_actual,
                "horas_transcurridas": horas,
                "factura_id": factura.id
            })
        return result
    else:
        # Todos los registros
        registros = obtener_registros(db)
        result = []
        
        for r in registros:
            factura = obtener_factura_por_registro(db, r.id)
            
            registro_data = {
                "id": r.id,
                "placa": r.placa_final,
                "hora_entrada": r.hora_deteccion.isoformat(),
                "hora_salida": factura.hora_salida.isoformat() if factura and factura.hora_salida else None,
                "estado": factura.estado if factura else "sin_factura",
                "camara_id": r.camara_id,
                "tipo_vehiculo": r.tipo_vehiculo,
                "url_imagen": f"/registros/{r.id}/imagen" if r.ruta_imagen else None
            }
            
            if factura:
                registro_data["factura_id"] = factura.id
                registro_data["valor_pagado"] = factura.valor_pagado
            
            result.append(registro_data)
        
        return result

@app.patch("/api/facturas/{vehiculo_id}/cerrar")
async def cerrar_factura_frontend(vehiculo_id: int, data: dict, db: Session = Depends(get_db)):
    """Cerrar factura de vehículo - Compatible con frontend"""
    from .crud import obtener_factura_por_registro, cerrar_factura
    from datetime import datetime
    
    # Obtener factura por registro_id (vehiculo_id es el registro_id)
    factura = obtener_factura_por_registro(db, vehiculo_id)
    
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    if factura.estado == "cerrado":
        raise HTTPException(status_code=400, detail="Factura ya está cerrada")
    
    # Obtener datos del request
    valor_pagado = data.get("valor_pagado", 0)
    hora_salida_str = data.get("hora_salida")
    
    # Parsear hora de salida
    if hora_salida_str:
        try:
            hora_salida = datetime.fromisoformat(hora_salida_str.replace('Z', '+00:00'))
        except:
            hora_salida = datetime.utcnow()
    else:
        hora_salida = datetime.utcnow()
    
    # Cerrar factura
    factura_cerrada = cerrar_factura(db, factura.id, valor_pagado, hora_salida)
    
    if factura_cerrada:
        return {
            "message": "Factura cerrada exitosamente",
            "valor": valor_pagado,
            "vehiculo_id": vehiculo_id,
            "factura_id": factura.id,
            "hora_salida": hora_salida.isoformat()
        }
    else:
        raise HTTPException(status_code=500, detail="Error cerrando factura")

@app.get("/")
async def root():
    """Endpoint de prueba"""
    return {
        "message": "Sistema de Detección de Placas - Backend Activo",
        "camaras_activas": len(camera_manager.active_cameras),
        "endpoints": {
            "camaras": "/camaras (GET, POST)",
            "api_camaras": "/api/camaras (GET, POST, DELETE)",
            "registros": "/registros (GET)",
            "api_registros": "/api/registros?estado=activo (GET)",
            "cerrar_factura": "/api/facturas/{id}/cerrar (PATCH)",
            "imagen": "/registros/{id}/imagen (GET)",
            "websocket": "/ws/camara/{cam_id}"
        }
    }

@app.on_event("shutdown")
async def shutdown_event():
    """Limpieza al cerrar la aplicación"""
    await camera_manager.stop_all_cameras()
    logger.info("Aplicación cerrada - todas las cámaras detenidas")