# api/core/camera_manager.py
import asyncio
import cv2
import base64
import traceback
import logging
from collections import defaultdict

from .detection import procesar_frame

logger = logging.getLogger(__name__)

# Límites para prevenir fugas de memoria
MAX_LISTENERS_PER_CAMERA = 50
MAX_ACTIVE_CAMERAS = 20

class CameraManager:
    """
    Gestiona procesamiento por cámara:
    - active_tasks: tarea asyncio por camara (processing loop)
    - listeners: set de websockets por camara para broadcast
    - Protecciones contra fugas de memoria
    """

    def __init__(self):
        self.active_tasks = {}       # cam_id -> asyncio.Task
        self.listeners = defaultdict(set)  # cam_id -> set(websocket)
        self._stopping = set()

    async def start_camera(self, cam_id: int, url: str, websocket=None, db=None):
        """
        Inicia la tarea de procesamiento si no existe.
        """
        # Validar límite de cámaras activas
        if len(self.active_tasks) >= MAX_ACTIVE_CAMERAS:
            logger.warning(f"Límite de cámaras activas alcanzado: {MAX_ACTIVE_CAMERAS}")
            raise RuntimeError(f"Máximo de {MAX_ACTIVE_CAMERAS} cámaras activas alcanzado")
        
        if cam_id not in self.active_tasks:
            loop = asyncio.get_event_loop()
            task = loop.create_task(self._process_loop(cam_id, url))
            self.active_tasks[cam_id] = task
            logger.info(f"🎬 Cámara {cam_id} iniciada desde URL: {url}")

    async def stop_camera(self, cam_id: int):
        """
        Marca la tarea para detenerse y cierra listeners.
        """
        if cam_id in self.active_tasks:
            self._stopping.add(cam_id)
            try:
                await asyncio.wait_for(self.active_tasks[cam_id], timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout esperando a que se detenga cámara {cam_id}")
            finally:
                self.active_tasks.pop(cam_id, None)
                self._stopping.discard(cam_id)
        # cerrar listeners (se espera que los websockets manejen desconexión del lado cliente)
        self.listeners.pop(cam_id, None)
        logger.info(f"Cámara {cam_id} detenida")

    async def stop_all_cameras(self):
        keys = list(self.active_tasks.keys())
        for cam_id in keys:
            await self.stop_camera(cam_id)
        logger.info("Todas las cámaras detenidas")

    async def register_listener(self, cam_id: int, websocket):
        """
        Añade websocket listener con validación de límite.
        """
        listener_count = len(self.listeners.get(cam_id, set()))
        
        if listener_count >= MAX_LISTENERS_PER_CAMERA:
            logger.warning(f"Límite de listeners para cámara {cam_id} alcanzado: {MAX_LISTENERS_PER_CAMERA}")
            raise RuntimeError(f"Máximo de {MAX_LISTENERS_PER_CAMERA} listeners por cámara alcanzado")
        
        self.listeners[cam_id].add(websocket)
        logger.info(f"Listener registrado para cámara {cam_id} ({listener_count + 1} total)")

    async def unregister_listener(self, cam_id: int, websocket):
        """
        Elimina websocket listener.
        """
        s = self.listeners.get(cam_id)
        if s and websocket in s:
            s.remove(websocket)
            logger.debug(f"Listener desregistrado de cámara {cam_id} ({len(s)} restantes)")

    async def _process_loop(self, cam_id: int, url: str):
        """
        Loop que abre la cámara y va procesando frames, enviando a todos los listeners.
        """
        logger.info(f"[_process_loop] 🎥 Iniciando loop cámara {cam_id} -> {url}")
        cap = cv2.VideoCapture(url)
        
        # Verificar que la cámara se abrió correctamente
        if not cap.isOpened():
            logger.error(f"[_process_loop] ❌ NO se pudo abrir la cámara: {url}")
            return
        
        logger.info(f"[_process_loop] ✅ Cámara abierta: {url}")
        frame_n = 0
        frame_sent = 0
        
        try:
            while True:
                if cam_id in self._stopping:
                    logger.info(f"[_process_loop] 🛑 Stop solicitado para {cam_id}")
                    break
                
                ret, frame = cap.read()
                
                if not ret:
                    logger.warning(f"[_process_loop] ⚠️ Error leyendo frame de {cam_id}, reintentando...")
                    await asyncio.sleep(1.0)
                    cap.release()
                    cap = cv2.VideoCapture(url)
                    if not cap.isOpened():
                        logger.error(f"[_process_loop] ❌ No se pudo reconectar a {url}")
                        break
                    continue
                
                frame_n += 1
                
                # procesar frame (anotaciones y DB si corresponde)
                frame_proc = procesar_frame(frame, frame_n)
                
                # codificar jpeg
                ok, buf = cv2.imencode('.jpg', frame_proc, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if not ok:
                    logger.debug(f"Error codificando frame {frame_n}")
                    continue
                
                data = buf.tobytes()
                
                # broadcast a listeners
                listeners = list(self.listeners.get(cam_id, []))
                
                if listeners:
                    frame_sent += 1
                    if frame_sent % 30 == 0:  # Log cada 30 frames
                        logger.debug(f"📤 Enviando frame #{frame_n} a {len(listeners)} listeners ({len(data)} bytes)")
                    
                    # enviar como bytes (WebSocket soporta send_bytes)
                    dead_websockets = []
                    for ws in listeners:
                        try:
                            await ws.send_bytes(data)
                        except Exception as e:
                            logger.debug(f"⚠️ No se pudo enviar a un listener: {e}")
                            dead_websockets.append(ws)
                    
                    # Limpiar listeners muertos
                    for ws in dead_websockets:
                        try:
                            await self.unregister_listener(cam_id, ws)
                        except Exception:
                            pass
                else:
                    if frame_n % 100 == 0:
                        logger.warning(f"[_process_loop] ⚠️ Cámara {cam_id} sin listeners (frame #{frame_n})")
                
                # pequeña pausa para no bloquear la loop del event loop
                await asyncio.sleep(0)  # cede control
                
        except Exception as e:
            logger.error(f"[_process_loop] ❌ Error en loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                cap.release()
                logger.info(f"[_process_loop] 🛑 Liberada cámara {cam_id}")
            except Exception:
                pass
            logger.info(f"[_process_loop] 🛑 Loop cámara {cam_id} finalizado (frames: {frame_n}, enviados: {frame_sent})")
