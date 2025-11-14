"""
Script para ejecutar el servidor FastAPI

Uso:
    python run_server.py

Para Colab con ngrok:
    python run_server.py --ngrok
"""

import uvicorn
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description='Ejecutar servidor FastAPI')
    parser.add_argument('--host', default='0.0.0.0', help='Host del servidor')
    parser.add_argument('--port', type=int, default=8000, help='Puerto del servidor')
    parser.add_argument('--ngrok', action='store_true', help='Usar ngrok para túnel público')
    parser.add_argument('--reload', action='store_true', help='Recarga automática en desarrollo')
    
    args = parser.parse_args()
    
    # Configurar ngrok si se solicita
    if args.ngrok:
        try:
            from pyngrok import ngrok
            # Crear túnel público
            public_url = ngrok.connect(args.port)
            print(f"🌐 Túnel ngrok activo: {public_url}")
            print(f"📱 Conecta tu frontend a: {public_url}")
        except ImportError:
            print("⚠️ Para usar ngrok instala: pip install pyngrok")
        except Exception as e:
            print(f"⚠️ Error configurando ngrok: {e}")
    
    # Configurar logging
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["default"],
        },
    }
    
    print("🚀 Iniciando servidor FastAPI...")
    print(f"📍 Dirección local: http://{args.host}:{args.port}")
    print("📚 Documentación: http://localhost:8000/docs")
    print("🔌 WebSocket ejemplo: ws://localhost:8000/ws/camara/1")
    
    # Ejecutar servidor
    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=log_config
    )

if __name__ == "__main__":
    main()