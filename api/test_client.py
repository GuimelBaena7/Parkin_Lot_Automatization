"""
Cliente de prueba para el backend FastAPI

Permite probar:
- Registro de cámaras
- Conexión WebSocket
- Visualización de stream procesado
"""

import asyncio
import websockets
import json
import requests
import base64
import cv2
import numpy as np
from datetime import datetime

class TestClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.ws_url = base_url.replace("http", "ws")

    def registrar_camara_test(self):
        """Registra una cámara de prueba"""
        camara_data = {
            "nombre": "Cámara Test",
            "url": "0"  # Webcam local
        }
        
        response = requests.post(f"{self.base_url}/camaras", json=camara_data)
        if response.status_code == 200:
            camara = response.json()
            print(f"✅ Cámara registrada: ID {camara['id']} - {camara['nombre']}")
            return camara['id']
        else:
            print(f"❌ Error registrando cámara: {response.text}")
            return None

    def listar_camaras(self):
        """Lista todas las cámaras"""
        response = requests.get(f"{self.base_url}/camaras")
        if response.status_code == 200:
            camaras = response.json()
            print(f"📹 Cámaras registradas: {len(camaras)}")
            for cam in camaras:
                print(f"  - ID {cam['id']}: {cam['nombre']} ({cam['url']})")
            return camaras
        else:
            print(f"❌ Error listando cámaras: {response.text}")
            return []

    async def conectar_websocket(self, cam_id, duracion=30):
        """Conecta al WebSocket de una cámara y muestra el stream"""
        ws_url = f"{self.ws_url}/ws/camara/{cam_id}"
        print(f"🔌 Conectando a WebSocket: {ws_url}")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print(f"✅ Conectado a cámara {cam_id}")
                print("📺 Mostrando stream (presiona 'q' para salir)...")
                
                start_time = datetime.now()
                frame_count = 0
                
                while True:
                    # Verificar tiempo límite
                    if (datetime.now() - start_time).seconds > duracion:
                        print(f"⏰ Tiempo límite alcanzado ({duracion}s)")
                        break
                    
                    try:
                        # Recibir mensaje
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        
                        if message.startswith("ERROR"):
                            print(f"❌ Error del servidor: {message}")
                            break
                        
                        # Parsear JSON
                        try:
                            data = json.loads(message)
                            if data.get("type") == "frame":
                                frame_count += 1
                                
                                # Decodificar frame
                                frame_b64 = data.get("frame", "")
                                if frame_b64:
                                    frame_bytes = base64.b64decode(frame_b64)
                                    frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
                                    frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
                                    
                                    if frame is not None:
                                        # Mostrar información de detección si existe
                                        if "detection" in data:
                                            det = data["detection"]
                                            print(f"🎯 Detección: {det['placa']} (conf: {det['confianza']:.2f}, dir: {det['direccion']})")
                                        
                                        # Mostrar frame
                                        cv2.imshow(f"Cámara {cam_id}", frame)
                                        
                                        # Salir con 'q'
                                        if cv2.waitKey(1) & 0xFF == ord('q'):
                                            print("👋 Saliendo...")
                                            break
                                
                                # Mostrar estadísticas cada 30 frames
                                if frame_count % 30 == 0:
                                    elapsed = (datetime.now() - start_time).seconds
                                    fps = frame_count / elapsed if elapsed > 0 else 0
                                    print(f"📊 Frames: {frame_count}, FPS: {fps:.1f}")
                        
                        except json.JSONDecodeError:
                            # Mensaje de texto simple (backward compatibility)
                            frame_bytes = base64.b64decode(message)
                            frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
                            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
                            
                            if frame is not None:
                                cv2.imshow(f"Cámara {cam_id}", frame)
                                if cv2.waitKey(1) & 0xFF == ord('q'):
                                    break
                    
                    except asyncio.TimeoutError:
                        print("⏰ Timeout esperando frame")
                        continue
                
        except Exception as e:
            print(f"❌ Error en WebSocket: {e}")
        finally:
            cv2.destroyAllWindows()

    def test_facturacion(self):
        """Prueba funcionalidad de facturación"""
        print("\n💰 Probando funcionalidad de facturación...")
        
        # 1. Obtener vehículos activos
        print("\n1️⃣ Obteniendo vehículos activos:")
        response = requests.get(f"{self.base_url}/api/registros?estado=activo")
        if response.status_code == 200:
            vehiculos_activos = response.json()
            print(f"✅ Vehículos activos: {len(vehiculos_activos)}")
            for v in vehiculos_activos:
                print(f"  - Placa: {v['placa']}, Valor actual: ${v.get('valor_actual', 0)}, Horas: {v.get('horas_transcurridas', 0)}")
            
            # 2. Cerrar factura si hay vehículos
            if vehiculos_activos:
                vehiculo = vehiculos_activos[0]
                print(f"\n2️⃣ Cerrando factura del vehículo {vehiculo['placa']}:")
                
                data_cierre = {
                    "valor_pagado": vehiculo.get('valor_actual', 3000),
                    "hora_salida": datetime.now().isoformat()
                }
                
                response = requests.patch(
                    f"{self.base_url}/api/facturas/{vehiculo['id']}/cerrar",
                    json=data_cierre
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Factura cerrada: ${result['valor']}")
                else:
                    print(f"❌ Error cerrando factura: {response.text}")
            else:
                print("⚠️ No hay vehículos activos para cerrar factura")
        else:
            print(f"❌ Error obteniendo vehículos activos: {response.text}")
    
    def crear_vehiculo_test(self):
        """Crear vehículo de prueba para facturación"""
        print("\n🚗 Creando vehículo de prueba...")
        
        # Simular detección creando registro directamente
        from datetime import datetime
        import sqlite3
        
        try:
            # Conectar a base de datos
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            
            # Crear registro
            cursor.execute("""
                INSERT INTO registros (camara_id, tipo_vehiculo, placa_final, confianza, hora_deteccion, direccion)
                VALUES (1, 'car', 'TEST123', 0.9, ?, 'entrada')
            """, (datetime.now(),))
            
            registro_id = cursor.lastrowid
            
            # Crear factura
            cursor.execute("""
                INSERT INTO facturas (registro_id, hora_entrada, estado, tarifa_por_hora)
                VALUES (?, ?, 'activo', 3000.0)
            """, (registro_id, datetime.now()))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Vehículo TEST123 creado con ID {registro_id}")
            return registro_id
            
        except Exception as e:
            print(f"❌ Error creando vehículo de prueba: {e}")
            return None

    def test_api_completa(self):
        """Prueba completa de la API"""
        print("🧪 Iniciando prueba completa del backend...")
        
        # 1. Listar cámaras existentes
        print("\n1️⃣ Listando cámaras existentes:")
        camaras = self.listar_camaras()
        
        # 2. Registrar nueva cámara
        print("\n2️⃣ Registrando nueva cámara:")
        cam_id = self.registrar_camara_test()
        
        # 3. Probar facturación
        self.test_facturacion()
        
        if cam_id:
            # 4. Listar cámaras actualizadas
            print("\n4️⃣ Listando cámaras actualizadas:")
            self.listar_camaras()
            
            return cam_id
        
        return None

async def main():
    """Función principal de prueba"""
    client = TestClient()
    
    # Probar API REST
    cam_id = client.test_api_completa()
    
    if cam_id:
        # Probar WebSocket
        await client.conectar_websocket(cam_id, duracion=60)
    else:
        print("❌ No se pudo probar WebSocket sin cámara registrada")

if __name__ == "__main__":
    print("🚀 Cliente de prueba para Backend FastAPI")
    print("📋 Asegúrate de que el servidor esté ejecutándose en http://localhost:8000")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Prueba interrumpida por el usuario")