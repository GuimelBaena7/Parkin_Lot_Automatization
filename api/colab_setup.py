"""
Script de configuración para Google Colab

Instala dependencias y configura ngrok para acceso público
"""

import subprocess
import sys
import os

def install_requirements():
    """Instala las dependencias necesarias"""
    print("📦 Instalando dependencias...")
    
    requirements = [
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0", 
        "websockets==12.0",
        "sqlalchemy==2.0.23",
        "pydantic==2.5.0",
        "opencv-python==4.8.1.78",
        "numpy==1.24.3",
        "ultralytics==8.3.0",
        "easyocr==1.7.0",
        "scipy==1.11.4",
        "filterpy==1.4.5",
        "rapidfuzz==3.5.2",
        "python-multipart==0.0.6",
        "pyngrok==7.0.0"
    ]
    
    for req in requirements:
        print(f"Instalando {req}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", req])

def setup_ngrok():
    """Configura ngrok para túnel público"""
    print("🌐 Configurando ngrok...")
    
    try:
        from pyngrok import ngrok
        print("✅ pyngrok instalado correctamente")
        
        # Opcional: configurar token de ngrok
        # ngrok.set_auth_token("tu_token_aqui")
        
        return True
    except ImportError:
        print("❌ Error importando pyngrok")
        return False

def copy_models():
    """Copia los modelos YOLO necesarios"""
    print("🤖 Verificando modelos YOLO...")
    
    models = ["yolo11n.pt", "license_plate_detector.pt"]
    
    for model in models:
        if os.path.exists(f"../{model}"):
            if not os.path.exists(model):
                import shutil
                shutil.copy(f"../{model}", model)
                print(f"✅ Copiado {model}")
        else:
            print(f"⚠️ Modelo {model} no encontrado en directorio padre")

def create_directories():
    """Crea directorios necesarios"""
    print("📁 Creando directorios...")
    
    dirs = [
        "static",
        "static/detecciones", 
        "core"
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"✅ Directorio {dir_path} creado")

def main():
    """Configuración completa para Colab"""
    print("🚀 Configurando Backend FastAPI para Google Colab")
    print("=" * 50)
    
    # 1. Crear directorios
    create_directories()
    
    # 2. Instalar dependencias
    install_requirements()
    
    # 3. Configurar ngrok
    setup_ngrok()
    
    # 4. Copiar modelos
    copy_models()
    
    print("\n✅ Configuración completada!")
    print("\n🎯 Próximos pasos:")
    print("1. python run_server.py --ngrok")
    print("2. Conectar frontend a la URL de ngrok")
    print("3. Registrar cámaras via API REST")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error en configuración: {e}")
        sys.exit(1)