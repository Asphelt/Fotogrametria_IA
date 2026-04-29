import os
import uuid
import asyncio
import json
import threading
from pathlib import Path
from datetime import datetime

from typing import List

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
MOCK: bool = os.getenv("MOCK", "false").lower() in ("true", "1", "yes")

# Importaciones relativas al paquete backend
import sys
sys.path.insert(0, str(Path(__file__).parent))

from almacenamiento import storage
from worker import process_job

app = FastAPI(title="Fotogrametría IA", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "image/bmp", "image/tiff", "image/x-tiff",
}


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/info")
async def info():
    return {"mock": MOCK, "version": "1.0"}


@app.post("/subir")
async def subir(imagenes: List[UploadFile] = File(...)):
    if len(imagenes) < 10:
        raise HTTPException(400, f"Se necesitan mínimo 10 imágenes (recibidas: {len(imagenes)})")
    if len(imagenes) > 200:
        raise HTTPException(400, "Máximo 200 imágenes por trabajo")

    for img in imagenes:
        ct = (img.content_type or "").lower()
        if ct not in ALLOWED_TYPES:
            raise HTTPException(400, f"Formato no soportado: {img.filename} ({ct})")

    job_id = str(uuid.uuid4())
    job_dir = storage.create_job_dir(job_id)

    # Guardar imágenes en disco (índice numérico para evitar colisiones de nombre)
    for i, img in enumerate(imagenes):
        raw = await img.read()
        ext = Path(img.filename).suffix.lower() or ".jpg"
        safe_name = f"{i:04d}{ext}"
        (job_dir / "images" / safe_name).write_bytes(raw)

    storage.update_job(job_id, {
        "id": job_id,
        "status": "en_cola",
        "progress": 0,
        "message": "En cola…",
        "image_count": len(imagenes),
        "model_path": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    })

    t = threading.Thread(target=process_job, args=(job_id, job_dir), daemon=True)
    t.start()

    return JSONResponse({"job_id": job_id})


@app.get("/trabajo/{job_id}")
async def get_trabajo(job_id: str):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado")
    return job


@app.get("/trabajos")
async def listar_trabajos():
    return storage.list_jobs()


@app.websocket("/ws/{job_id}")
async def websocket_progreso(ws: WebSocket, job_id: str):
    await ws.accept()
    ultimo_pct = -1
    try:
        while True:
            job = storage.get_job(job_id)
            if not job:
                await ws.send_text(json.dumps({"error": "Trabajo no encontrado"}))
                break

            if job["progress"] != ultimo_pct or job["status"] in ("completado", "error"):
                await ws.send_text(json.dumps(job))
                ultimo_pct = job["progress"]

            if job["status"] in ("completado", "error"):
                break

            await asyncio.sleep(0.4)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.get("/modelo/{job_id}")
async def descargar_modelo(job_id: str):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado")
    if job["status"] != "completado":
        raise HTTPException(400, "Modelo no disponible todavía")

    model_path = storage.get_model_path(job_id)
    if not model_path:
        raise HTTPException(404, "Archivo de modelo no encontrado en disco")

    suffix = model_path.suffix.lower()
    media = "model/gltf-binary" if suffix == ".glb" else "application/octet-stream"
    return FileResponse(
        str(model_path),
        media_type=media,
        filename=f"modelo_{job_id[:8]}{suffix}",
    )
