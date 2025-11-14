"""
Configuración de Base de Datos SQLite con SQLAlchemy

Maneja:
- Conexión a SQLite
- Sesiones de base de datos
- Configuración del engine
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

UNIQUE_FOLDER_PATH = "detecciones_unicas"
os.makedirs(UNIQUE_FOLDER_PATH, exist_ok=True)


# URL de la base de datos SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./estacionamiento_camaras.db"

# Crear engine con configuración para SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Necesario para SQLite
)

# Crear SessionLocal para manejar sesiones de DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos
Base = declarative_base()