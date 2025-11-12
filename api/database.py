# api/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Ruta a la BD que tu main.py está llenando:
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_FILENAME = "estacionamiento.db"
DB_PATH = os.path.join(BASE_DIR, DB_FILENAME)
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Engine y sesión
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Carpeta de imágenes (misma que tu main.py)
UNIQUE_FOLDER_PATH = os.path.join(BASE_DIR, "detecciones_unicas")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Crea tablas si no existen (si tu main.py ya creó la tabla con sqlite3, esto
    # sólo ayuda a que SQLAlchemy conozca la tabla si coincide la estructura)
    from . import models  # importa modelos para que metadata se registre
    Base.metadata.create_all(bind=engine)
