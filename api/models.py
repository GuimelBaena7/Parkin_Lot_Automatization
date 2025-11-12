# api/models.py
from sqlalchemy import Column, Integer, String
from .database import Base

class Registro(Base):
    __tablename__ = "registros"

    id = Column(Integer, primary_key=True, index=True)
    tipo_vehiculo = Column(String, index=True)
    placa_final = Column(String, index=True)
    hora_entrada = Column(String)       # tu main.py guarda texto YYYY-MM-DD HH:MM:SS
    direccion = Column(String)
    url_imagen = Column(String)
    id_sort_original = Column(Integer)
    frames_hasta_placa = Column(Integer)
