# api/crud.py
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from . import models, schemas

def create_registro(db: Session, registro: schemas.RegistroCreate) -> models.Registro:
    hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_reg = models.Registro(
        tipo_vehiculo=registro.tipo_vehiculo,
        placa_final=registro.placa_final,
        hora_entrada=hora,
        direccion=registro.direccion or "",
        url_imagen=registro.url_imagen or "",
        id_sort_original=registro.id_sort_original,
        frames_hasta_placa=registro.frames_hasta_placa or 0,
    )
    db.add(db_reg)
    db.commit()
    db.refresh(db_reg)
    return db_reg

def get_registro(db: Session, registro_id: int) -> Optional[models.Registro]:
    return db.query(models.Registro).filter(models.Registro.id == registro_id).first()

def get_registros(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    placa: Optional[str] = None,
    tipo_vehiculo: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> List[models.Registro]:
    q = db.query(models.Registro)
    if placa:
        q = q.filter(models.Registro.placa_final.contains(placa))
    if tipo_vehiculo:
        q = q.filter(models.Registro.tipo_vehiculo == tipo_vehiculo)
    if fecha_inicio:
        q = q.filter(models.Registro.hora_entrada >= fecha_inicio)
    if fecha_fin:
        q = q.filter(models.Registro.hora_entrada <= fecha_fin)
    return q.order_by(models.Registro.hora_entrada.desc()).offset(skip).limit(limit).all()

def update_registro(db: Session, registro_id: int, registro_update: schemas.RegistroUpdate) -> Optional[models.Registro]:
    db_reg = db.query(models.Registro).filter(models.Registro.id == registro_id).first()
    if not db_reg:
        return None
    for key, value in registro_update.dict(exclude_unset=True).items():
        setattr(db_reg, key, value)
    db.commit()
    db.refresh(db_reg)
    return db_reg

def delete_registro(db: Session, registro_id: int) -> bool:
    db_reg = db.query(models.Registro).filter(models.Registro.id == registro_id).first()
    if not db_reg:
        return False
    db.delete(db_reg)
    db.commit()
    return True
