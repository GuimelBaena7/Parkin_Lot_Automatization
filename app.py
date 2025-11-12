# app.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import cv2, base64, asyncio
import numpy as np
from main import detectar_frame  # importamos tu función principal

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # puedes restringir luego al dominio de tu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/video")
async def video_stream(websocket: WebSocket):
    await websocket.accept()
    cap = cv2.VideoCapture(0)  # o RTSP / video file
    frame_nmr = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_nmr += 1

            # Procesar el frame con tu detección completa
            frame_processed = detectar_frame(frame, frame_nmr)

            # Codificar y enviar al frontend
            _, buffer = cv2.imencode('.jpg', frame_processed)
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            await websocket.send_text(frame_b64)

            await asyncio.sleep(0.03)  # ~30 FPS máx

    except Exception as e:
        print("Error WebSocket:", e)
    finally:
        cap.release()
        await websocket.close()
