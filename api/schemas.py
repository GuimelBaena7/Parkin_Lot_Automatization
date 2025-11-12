# api/schemas.py
from pydantic import BaseModel
from typing import Optional

class RegistroBase(BaseModel):
    tipo_vehiculo: Optional[str] = None
    placa_final: Optional[str] = None
    direccion: Optional[str] = None
    url_imagen: Optional[str] = None
    id_sort_original: Optional[int] = None
    frames_hasta_placa: Optional[int] = None

class RegistroCreate(RegistroBase):
    tipo_vehiculo: str
    placa_final: str

class RegistroUpdate(RegistroBase):
    pass

class RegistroResponse(RegistroBase):
    id: int
    hora_entrada: Optional[str] = None

    class Config:
        orm_mode = True
