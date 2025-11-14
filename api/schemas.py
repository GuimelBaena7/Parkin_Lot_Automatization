"""
Esquemas Pydantic para Validación de Datos

Define la estructura de datos para:
- Requests del frontend
- Responses del backend
- Validación automática
"""

from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional

class CamaraCreate(BaseModel):
    """
    Esquema para crear una nueva cámara
    
    El frontend envía:
    {
        "nombre": "Camara Entrada",
        "url": "rtsp://mi-camara"
    }
    """
    nombre: str
    url: str
    
    @validator('nombre')
    def validar_nombre(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('El nombre debe tener al menos 3 caracteres')
        return v.strip()
    
    @validator('url')
    def validar_url(cls, v):
        if not v or not (v.startswith('rtsp://') or v.startswith('http://') or v.startswith('https://') or v.isdigit()):
            raise ValueError('URL debe ser rtsp://, http://, https:// o número de cámara')
        return v

class CamaraResponse(BaseModel):
    """
    Esquema para respuesta de cámara
    """
    id: int
    nombre: str
    url: str
    activa: int
    fecha_registro: datetime
    
    class Config:
        from_attributes = True

class RegistroResponse(BaseModel):
    id: int
    camara_id: int
    tipo_vehiculo: str
    placa_final: str
    confianza: float
    hora_deteccion: datetime
    direccion: str
    ruta_imagen: Optional[str] = None
    url_imagen: Optional[str] = None
    
    class Config:
        from_attributes = True