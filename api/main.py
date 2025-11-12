# api/app.py
import os
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from sqlalchemy.orm import Session

from .database import get_db, init_db, UNIQUE_FOLDER_PATH
from . import crud, schemas, models

app = FastAPI(title="Parqueadero API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar carpeta donde tu pipeline guarda las imágenes
# UNIQUE_FOLDER_PATH se define en database.py (ruta absoluta)
os.makedirs(UNIQUE_FOLDER_PATH, exist_ok=True)

# Montar archivos estáticos para que FastAPI sirva las imágenes
app.mount("/static/detecciones", StaticFiles(directory=UNIQUE_FOLDER_PATH), name="detecciones")

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def root():
    return {"message": "API activa", "docs": "/docs"}

# --- Obtener todos los registros (con filtros y paginado) ---
@app.get("/registros", response_model=List[schemas.RegistroResponse])
def get_registros(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=2000),
    placa: Optional[str] = Query(None),
    tipo_vehiculo: Optional[str] = Query(None),
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    regs = crud.get_registros(db=db, skip=skip, limit=limit, placa=placa, tipo_vehiculo=tipo_vehiculo, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    # Ajuste: convertir url_imagen absoluta a ruta accesible por frontend (/static/detecciones/...)
    for r in regs:
        if r.url_imagen:
            filename = os.path.basename(r.url_imagen)
            r.url_imagen = f"/static/detecciones/{filename}"
    return regs

# --- Obtener un registro por id ---
@app.get("/registros/{registro_id}", response_model=schemas.RegistroResponse)
def get_registro(registro_id: int, db: Session = Depends(get_db)):
    reg = crud.get_registro(db, registro_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    if reg.url_imagen:
        reg.url_imagen = f"/static/detecciones/{os.path.basename(reg.url_imagen)}"
    return reg

# --- Obtener la imagen asociada a un registro (devuelve file) ---
@app.get("/registros/{registro_id}/imagen")
def get_registro_image(registro_id: int, db: Session = Depends(get_db)):
    reg = crud.get_registro(db, registro_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    path = reg.url_imagen
    if not path or not os.path.exists(path):
        # intentar resolver en UNIQUE_FOLDER_PATH por basename
        basename = os.path.basename(path) if path else None
        if basename:
            candidate = os.path.join(UNIQUE_FOLDER_PATH, basename)
            if os.path.exists(candidate):
                return FileResponse(candidate, media_type="image/jpeg", filename=basename)
        raise HTTPException(status_code=404, detail=f"Imagen no encontrada en path: {path}")
    return FileResponse(path, media_type="image/jpeg", filename=os.path.basename(path))

# --- Obtener imagen por nombre de archivo (si prefieres usar filename directo) ---
@app.get("/images/{filename}")
def get_image_filename(filename: str):
    full = os.path.join(UNIQUE_FOLDER_PATH, filename)
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(full, media_type="image/jpeg", filename=filename)

# --- Crear nuevo registro (útil si quieres insertar desde frontend) ---
@app.post("/registros", response_model=schemas.RegistroResponse, status_code=201)
def create_registro(registro_in: schemas.RegistroCreate, db: Session = Depends(get_db)):
    reg = crud.create_registro(db, registro_in)
    if reg.url_imagen:
        reg.url_imagen = f"/static/detecciones/{os.path.basename(reg.url_imagen)}"
    return reg

# --- Actualizar registro completo (PUT) ---
@app.put("/registros/{registro_id}", response_model=schemas.RegistroResponse)
def update_registro(registro_id: int, registro_in: schemas.RegistroUpdate, db: Session = Depends(get_db)):
    updated = crud.update_registro(db, registro_id, registro_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    if updated.url_imagen:
        updated.url_imagen = f"/static/detecciones/{os.path.basename(updated.url_imagen)}"
    return updated

# --- Eliminar registro ---
@app.delete("/registros/{registro_id}", status_code=204)
def delete_registro(registro_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_registro(db, registro_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"detail": "Eliminado"}
