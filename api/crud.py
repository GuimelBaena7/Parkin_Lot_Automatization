from sqlalchemy.orm import Session
from datetime import datetime
from models import Camara, Registro, Factura
from schemas import CamaraCreate

def crear_camara(db: Session, camara: CamaraCreate):
    db_camara = Camara(
        nombre=camara.nombre,
        url=camara.url,
        activa=1,
        fecha_registro=datetime.utcnow()
    )
    db.add(db_camara)
    db.commit()
    db.refresh(db_camara)
    return db_camara

def obtener_camaras(db: Session):
    return db.query(Camara).all()

def obtener_camara_por_id(db: Session, camara_id: int):
    return db.query(Camara).filter(Camara.id == camara_id).first()

def eliminar_camara(db: Session, camara_id: int):
    camara = db.query(Camara).filter(Camara.id == camara_id).first()
    if camara:
        db.delete(camara)
        db.commit()
        return True
    return False

def crear_registro(db: Session, camara_id: int, tipo_vehiculo: str, placa_final: str, 
                  confianza: float, direccion: str, ruta_imagen: str = None, url_imagen: str = None):
    db_registro = Registro(
        camara_id=camara_id,
        tipo_vehiculo=tipo_vehiculo,
        placa_final=placa_final,
        confianza=confianza,
        hora_deteccion=datetime.utcnow(),
        direccion=direccion,
        ruta_imagen=ruta_imagen,
        url_imagen=url_imagen
    )
    db.add(db_registro)
    db.commit()
    db.refresh(db_registro)
    return db_registro

def obtener_registros(db: Session, limit: int = 100):
    return db.query(Registro).order_by(Registro.hora_deteccion.desc()).limit(limit).all()

def obtener_registro_por_id(db: Session, registro_id: int):
    return db.query(Registro).filter(Registro.id == registro_id).first()

# ==================== FUNCIONES DE FACTURACIÓN ====================

def crear_factura(db: Session, registro_id: int):
    """Crear factura automáticamente cuando se detecta un vehículo"""
    registro = obtener_registro_por_id(db, registro_id)
    if not registro:
        return None
    
    # Verificar si ya existe factura
    factura_existente = db.query(Factura).filter(Factura.registro_id == registro_id).first()
    if factura_existente:
        return factura_existente
    
    db_factura = Factura(
        registro_id=registro_id,
        hora_entrada=registro.hora_deteccion,
        estado="activo",
        tarifa_por_hora=3000.0
    )
    db.add(db_factura)
    db.commit()
    db.refresh(db_factura)
    return db_factura

def obtener_facturas_activas(db: Session):
    """Obtener todas las facturas activas (vehículos en el parqueadero)"""
    return db.query(Factura).filter(Factura.estado == "activo").all()

def cerrar_factura(db: Session, factura_id: int, valor_pagado: float, hora_salida: datetime = None):
    """Cerrar factura cuando el vehículo sale"""
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        return None
    
    if hora_salida is None:
        hora_salida = datetime.utcnow()
    
    factura.hora_salida = hora_salida
    factura.valor_pagado = valor_pagado
    factura.estado = "cerrado"
    
    db.commit()
    db.refresh(factura)
    return factura

def obtener_factura_por_registro(db: Session, registro_id: int):
    """Obtener factura por ID de registro"""
    return db.query(Factura).filter(Factura.registro_id == registro_id).first()

def calcular_valor_factura(hora_entrada: datetime, hora_salida: datetime = None, tarifa_por_hora: float = 3000.0):
    """Calcular valor a pagar basado en tiempo transcurrido"""
    if hora_salida is None:
        hora_salida = datetime.utcnow()
    
    tiempo_transcurrido = hora_salida - hora_entrada
    horas = tiempo_transcurrido.total_seconds() / 3600
    
    # Mínimo 1 hora
    if horas < 1:
        horas = 1
    
    # Redondear hacia arriba
    import math
    horas_cobrar = math.ceil(horas)
    
    return horas_cobrar * tarifa_por_hora, horas_cobrar

