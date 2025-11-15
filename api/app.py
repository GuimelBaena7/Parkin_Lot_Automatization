"""
FastAPI Backend para Sistema de Detección de Placas con Múltiples Cámaras

Funcionalidades:
- API REST para administrar cámaras dinámicamente
- WebSockets independientes por cámara (/ws/camara/{cam_id})
- Procesamiento YOLO + OCR en tiempo real
- Base de datos SQLite con SQLAlchemy
- Guardado de imágenes detectadas en /static/detecciones
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
import asyncio
import logging
import json
import cv2
import numpy as np
from core.camera_manager import CameraManager
import os
os.makedirs("static", exist_ok=True)

# Nota: Se ha eliminado la dependencia de base de datos. El sistema acepta
# URLs de cámara o frames locales enviados por el frontend.

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

# No hay dependencia de base de datos en esta versión simplificada

# ==================== ENDPOINTS REST ====================

# Se removieron los endpoints REST que dependían de la base de datos. 
# Este backend ahora acepta únicamente conexiones WebSocket donde el frontend
# envía la URL de la cámara o frames locales.

# ==================== WEBSOCKETS DINÁMICOS ====================

# El endpoint para cámaras registradas en BD fue eliminado. Use /ws/camara-directa
# para enviar una URL o frames locales desde el frontend.


@app.websocket("/ws/camara-directa")
async def websocket_camara_directa(websocket: WebSocket):
    """
    WebSocket para procesar cámara sin registrar en BD
    
    El frontend envía:
    1. Primero: {"type": "camera_url", "url": "rtsp://mi-camara"}
    2. O: {"type": "camera_local"} para usar cámara del dispositivo
    3. Luego: frames en base64 si es cámara local
    
    Casos de uso:
    - Cámara IP sin registrar: Enviar URL directamente
    - Cámara local (celular/PC): Capturar frames en frontend y enviar
    """
    await websocket.accept()
    logger.info("✅ Cliente conectado a cámara directa")
    
    cam_id = None
    camera_task = None
    config = None
    
    try:
        # Esperar configuración inicial (JSON texto)
        first_message = await websocket.receive_text()
        config = json.loads(first_message)
        logger.info(f"📝 Configuración recibida: {config}")
        
        if config.get("type") == "camera_url":
            # Cámara IP sin registrar
            camera_url = config.get("url")
            if not camera_url:
                await websocket.send_text(json.dumps({"error": "URL de cámara requerida"}))
                await websocket.close()
                return
            
            # Usar hash de URL como cam_id temporal
            cam_id = f"url_{hash(camera_url) % 1000000}"
            logger.info(f"🎥 Cámara URL: {camera_url} (ID: {cam_id})")
            
            # Registrar websocket como listener PRIMERO
            await camera_manager.register_listener(cam_id, websocket)
            
            # LUEGO iniciar el loop de procesamiento
            await camera_manager.start_camera(cam_id, camera_url)
            
            # Mantener conexión viva (el CameraManager enviará frames)
            while True:
                try:
                    # Esperar a que el cliente cierre o envíe algo
                    msg = await websocket.receive_text()
                    logger.debug(f"Ping recibido: {msg}")
                except WebSocketDisconnect:
                    logger.info(f"🔌 Cliente desconectado de {cam_id}")
                    break
                except Exception as e:
                    logger.error(f"❌ Error en websocket {cam_id}: {e}")
                    break
        
        elif config.get("type") == "camera_local":
            # Cámara local - el frontend enviará frames
            cam_id = "local_" + str(abs(hash(str(websocket))))
            logger.info(f"📱 Cámara LOCAL (ID: {cam_id})")
            
            # Para cámara local, recibir y procesar frames del frontend
            while True:
                try:
                    data = await websocket.receive_bytes()
                    logger.debug(f"📸 Frame recibido para {cam_id} ({len(data)} bytes)")
                    
                    # Procesar frame recibido
                    import numpy as np
                    nparr = np.frombuffer(data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        # Procesar y enviar de vuelta
                        from core.detection import procesar_frame
                        frame_proc = procesar_frame(frame, 0)
                        ok, buf = cv2.imencode('.jpg', frame_proc, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                        if ok:
                            logger.debug(f"✅ Frame procesado, enviando {len(buf.tobytes())} bytes")
                            await websocket.send_bytes(buf.tobytes())
                except WebSocketDisconnect:
                    logger.info(f"🔌 Cliente local desconectado: {cam_id}")
                    break
                except Exception as e:
                    logger.error(f"❌ Error procesando frame local: {e}")
                    await asyncio.sleep(0.1)
        
    except WebSocketDisconnect:
        logger.info("🔌 Cliente desconectado")
    except Exception as e:
        logger.error(f"❌ Error en WebSocket cámara directa: {e}")
    finally:
        # Limpieza
        try:
            if cam_id:
                if config and config.get("type") == "camera_url":
                    await camera_manager.unregister_listener(cam_id, websocket)
                    await camera_manager.stop_camera(cam_id)
                    logger.info(f"🛑 Cámara URL {cam_id} detenida")
                else:
                    logger.info(f"🛑 Cámara LOCAL {cam_id} detenida")
        except Exception as e:
            logger.error(f"Error en cleanup: {e}")

# ==================== ENDPOINTS DE FACTURACIÓN ====================

# Funcionalidades relacionadas con facturación y registros han sido removidas
# para simplificar el backend a un servicio de procesamiento de cámaras sin DB.

@app.get("/")
async def root():
    """Endpoint de prueba"""
    return {
        "message": "Sistema de Detección de Placas - Backend Activo (sin DB)",
        "camaras_activas": len(camera_manager.active_tasks),
        "endpoints": {
            "websocket_directo": "/ws/camara-directa"
        }
    }

@app.on_event("shutdown")
async def shutdown_event():
    """Limpieza al cerrar la aplicación"""
    await camera_manager.stop_all_cameras()
    logger.info("Backend cerrado - todas las cámaras detenidas")


# ==================== MODELOS PYDANTIC ====================

class CameraRequest(BaseModel):
    """Modelo para crear/actualizar cámara"""
    nombre: str
    url: str = "local://camera"  # URL por defecto para cámaras locales
    tipo: str = "ip"  # "ip" o "local"

class RegistroRequest(BaseModel):
    """Modelo para crear registro"""
    placa: str
    timestamp: str = None
    imagen_url: str = None
    estado: str = "activo"

# ==================== ALMACENAMIENTO EN MEMORIA ====================

# Diccionarios para almacenar datos (en producción usar base de datos)
cameras_db = {}  # {camera_id: {"nombre": str, "url": str, "tipo": str, "creado": datetime}}
registros_db = {}  # {registro_id: {"placa": str, "timestamp": str, "estado": str, ...}}
camera_counter = 0
registro_counter = 0

# ==================== ENDPOINTS REST PARA CÁMARAS ====================

@app.get("/api/camaras")
async def get_camaras():
    """Obtener lista de cámaras registradas"""
    return {
        "camaras": list(cameras_db.values()),
        "total": len(cameras_db),
        "activas": len(camera_manager.active_tasks)
    }

@app.post("/api/camaras")
async def create_camera(camera: CameraRequest):
    """Crear nueva cámara"""
    global camera_counter
    camera_counter += 1
    camera_id = camera_counter
    
    cameras_db[camera_id] = {
        "id": camera_id,
        "nombre": camera.nombre,
        "url": camera.url,
        "tipo": camera.tipo,
        "creado": datetime.now().isoformat(),
        "estado": "inactivo"
    }
    
    logger.info(f"Cámara creada: {camera.nombre} (ID: {camera_id})")
    return {
        "success": True,
        "camera_id": camera_id,
        "message": "Cámara creada exitosamente"
    }

@app.get("/api/camaras/{camera_id}")
async def get_camera(camera_id: int):
    """Obtener detalles de cámara específica"""
    if camera_id not in cameras_db:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    
    camera = cameras_db[camera_id]
    camera["activa"] = camera_id in camera_manager.active_tasks
    camera["listeners"] = len(camera_manager.listeners.get(camera_id, set()))
    return camera

@app.put("/api/camaras/{camera_id}")
async def update_camera(camera_id: int, camera: CameraRequest):
    """Actualizar cámara"""
    if camera_id not in cameras_db:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    
    cameras_db[camera_id].update({
        "nombre": camera.nombre,
        "url": camera.url,
        "tipo": camera.tipo
    })
    
    logger.info(f"Cámara actualizada: {camera.nombre} (ID: {camera_id})")
    return {"success": True, "message": "Cámara actualizada"}

@app.delete("/api/camaras/{camera_id}")
async def delete_camera(camera_id: int):
    """Eliminar cámara"""
    if camera_id not in cameras_db:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    
    # Detener procesamiento si está activo
    if camera_id in camera_manager.active_tasks:
        await camera_manager.stop_camera(camera_id)
    
    del cameras_db[camera_id]
    logger.info(f"Cámara eliminada (ID: {camera_id})")
    return {"success": True, "message": "Cámara eliminada"}

# ==================== ENDPOINTS REST PARA REGISTROS ====================

@app.get("/api/registros")
async def get_registros(estado: str = None):
    """Obtener registros de detecciones"""
    registros = list(registros_db.values())
    
    if estado:
        registros = [r for r in registros if r.get("estado") == estado]
    
    return {
        "registros": registros,
        "total": len(registros),
        "filtrado_por": estado or "ninguno"
    }

@app.post("/api/registros")
async def create_registro(registro: RegistroRequest):
    """Crear nuevo registro de detección"""
    global registro_counter
    registro_counter += 1
    registro_id = registro_counter
    
    registros_db[registro_id] = {
        "id": registro_id,
        "placa": registro.placa,
        "timestamp": registro.timestamp or datetime.now().isoformat(),
        "imagen_url": registro.imagen_url,
        "estado": registro.estado
    }
    
    logger.info(f"Registro creado: {registro.placa}")
    return {
        "success": True,
        "registro_id": registro_id,
        "message": "Registro creado exitosamente"
    }

@app.get("/api/registros/{registro_id}")
async def get_registro(registro_id: int):
    """Obtener detalles de registro"""
    if registro_id not in registros_db:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return registros_db[registro_id]

@app.delete("/api/registros/{registro_id}")
async def delete_registro(registro_id: int):
    """Eliminar registro"""
    if registro_id not in registros_db:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    
    del registros_db[registro_id]
    logger.info(f"Registro eliminado (ID: {registro_id})")
    return {"success": True, "message": "Registro eliminado"}

# ==================== ENDPOINTS DE ESTADÍSTICAS ====================

@app.get("/api/stats")
async def get_stats():
    """Obtener estadísticas del sistema"""
    return {
        "camaras_total": len(cameras_db),
        "camaras_activas": len(camera_manager.active_tasks),
        "registros_total": len(registros_db),
        "registros_activos": len([r for r in registros_db.values() if r.get("estado") == "activo"]),
        "conexiones_simultaneas": sum(len(listeners) for listeners in camera_manager.listeners.values()),
        "timestamp": datetime.now().isoformat()
    }
    await camera_manager.stop_all_cameras()
    logger.info("Aplicación cerrada - todas las cámaras detenidas")