from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Camara(Base):
    __tablename__ = "camaras"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    url = Column(String, nullable=False)
    activa = Column(Integer, default=1)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    
    registros = relationship("Registro", back_populates="camara")

class Registro(Base):
    __tablename__ = "registros"
    
    id = Column(Integer, primary_key=True, index=True)
    camara_id = Column(Integer, ForeignKey("camaras.id"))
    tipo_vehiculo = Column(String, default="car")
    placa_final = Column(String, nullable=False)
    confianza = Column(Float, default=0.0)
    hora_deteccion = Column(DateTime, default=datetime.utcnow)
    direccion = Column(String, default="indeterminado")
    ruta_imagen = Column(String)
    url_imagen = Column(String)
    
    camara = relationship("Camara", back_populates="registros")
    factura = relationship("Factura", back_populates="registro", uselist=False)

class Factura(Base):
    __tablename__ = "facturas"
    
    id = Column(Integer, primary_key=True, index=True)
    registro_id = Column(Integer, ForeignKey("registros.id"), unique=True)
    hora_entrada = Column(DateTime, nullable=False)
    hora_salida = Column(DateTime)
    valor_pagado = Column(Float, default=0.0)
    estado = Column(String, default="activo")  # activo, cerrado
    tarifa_por_hora = Column(Float, default=3000.0)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    
    registro = relationship("Registro", back_populates="factura")