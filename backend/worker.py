import os
import sys
import time
import struct
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from almacenamiento import storage

MOCK: bool = os.getenv("MOCK", "false").lower() in ("true", "1", "yes")

COLMAP_BIN = shutil.which("colmap") or "/opt/homebrew/bin/colmap"

# En Linux sin display usamos xvfb-run para que COLMAP pueda crear contexto OpenGL
_IS_LINUX = sys.platform == "linux"
_XVFB = shutil.which("xvfb-run")
_COLMAP_ENV = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}


def _colmap_cmd(args: List[str]) -> List[str]:
    """Prefija con xvfb-run en Linux si está disponible."""
    if _IS_LINUX and _XVFB:
        return [_XVFB, "-a", "--"] + args
    return args


def _colmap_supports_use_gpu() -> bool:
    """COLMAP ≥4.0 eliminó la flag --SiftExtraction.use_gpu."""
    r = subprocess.run(
        [COLMAP_BIN, "feature_extractor", "--help"],
        capture_output=True, text=True
    )
    return "use_gpu" in (r.stdout + r.stderr)


_USE_GPU_FLAG: bool = False  # se evalúa la primera vez que se necesita
_GPU_FLAG_CHECKED: bool = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def set_progress(job_id: str, progress: int, status: str, message: str) -> None:
    job = storage.get_job(job_id) or {}
    job.update({"progress": progress, "status": status, "message": message})
    storage.update_job(job_id, job)


# ── GLB mínimo (cubo unitario con material azul) ─────────────────────────────

def _pad4(data: bytes) -> bytes:
    rem = len(data) % 4
    return data + b"\x00" * (4 - rem) if rem else data


def crear_glb_cubo() -> bytes:
    positions = [
        -0.5,-0.5, 0.5,  0.5,-0.5, 0.5,  0.5, 0.5, 0.5, -0.5, 0.5, 0.5,
        -0.5,-0.5,-0.5,  0.5,-0.5,-0.5,  0.5, 0.5,-0.5, -0.5, 0.5,-0.5,
    ]
    indices = [
        0,1,2, 0,2,3,   5,4,7, 5,7,6,
        4,0,3, 4,3,7,   1,5,6, 1,6,2,
        3,2,6, 3,6,7,   4,5,1, 4,1,0,
    ]
    normals = [
         0, 0, 1,  0, 0, 1,  0, 0, 1,  0, 0, 1,
         0, 0,-1,  0, 0,-1,  0, 0,-1,  0, 0,-1,
    ]

    pos_bytes  = _pad4(struct.pack(f"{len(positions)}f", *positions))
    norm_bytes = _pad4(struct.pack(f"{len(normals)}f",   *normals))
    idx_bytes  = _pad4(struct.pack(f"{len(indices)}H",   *indices))
    bin_data   = idx_bytes + pos_bytes + norm_bytes
    bin_len    = len(bin_data)

    off_idx  = 0
    len_idx  = len(idx_bytes)
    off_pos  = len_idx
    len_pos  = len(pos_bytes)
    off_norm = len_idx + len_pos
    len_norm = len(norm_bytes)

    gltf = {
        "asset": {"version": "2.0", "generator": "Fotogrametria-App-Mock"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes":  [{"mesh": 0, "name": "Cubo"}],
        "meshes": [{"name": "Cubo", "primitives": [{
            "attributes": {"POSITION": 1, "NORMAL": 2},
            "indices": 0, "material": 0
        }]}],
        "materials": [{"name": "Material", "pbrMetallicRoughness": {
            "baseColorFactor": [0.3, 0.6, 1.0, 1.0],
            "metallicFactor": 0.05, "roughnessFactor": 0.7
        }}],
        "accessors": [
            {"bufferView":0,"componentType":5123,"count":len(indices),"type":"SCALAR","max":[max(indices)],"min":[0]},
            {"bufferView":1,"componentType":5126,"count":8,"type":"VEC3","max":[0.5,0.5,0.5],"min":[-0.5,-0.5,-0.5]},
            {"bufferView":2,"componentType":5126,"count":8,"type":"VEC3","max":[1,1,1],"min":[-1,-1,-1]},
        ],
        "bufferViews": [
            {"buffer":0,"byteOffset":off_idx, "byteLength":len_idx, "target":34963},
            {"buffer":0,"byteOffset":off_pos, "byteLength":len_pos, "target":34962},
            {"buffer":0,"byteOffset":off_norm,"byteLength":len_norm,"target":34962},
        ],
        "buffers": [{"byteLength": bin_len}],
    }

    raw_json = json.dumps(gltf, separators=(",",":")).encode()
    rem = len(raw_json) % 4
    json_bytes = raw_json + b" " * (4 - rem) if rem else raw_json
    total = 12 + 8 + len(json_bytes) + 8 + bin_len

    glb  = struct.pack("<III", 0x46546C67, 2, total)
    glb += struct.pack("<II",  len(json_bytes), 0x4E4F534A)
    glb += json_bytes
    glb += struct.pack("<II",  bin_len, 0x004E4942)
    glb += bin_data
    return glb


# ── Modo MOCK ─────────────────────────────────────────────────────────────────

def _process_mock(job_id: str, job_dir: Path) -> None:
    pasos = [
        (5,  "procesando", "Validando imágenes…"),
        (15, "procesando", "Preprocesando imágenes…"),
        (28, "procesando", "Extrayendo características SIFT…"),
        (40, "entrenando", "Inicializando Instant-NGP…"),
        (52, "entrenando", "Entrenando modelo (iteración 1/3)…"),
        (65, "entrenando", "Entrenando modelo (iteración 2/3)…"),
        (78, "entrenando", "Entrenando modelo (iteración 3/3)…"),
        (87, "exportando", "Extrayendo geometría 3D…"),
        (93, "exportando", "Generando malla poligonal…"),
        (97, "exportando", "Exportando a formato .GLB…"),
    ]
    for pct, status, msg in pasos:
        time.sleep(1.4)
        set_progress(job_id, pct, status, msg)

    model_path = job_dir / "output" / "modelo.glb"
    model_path.write_bytes(crear_glb_cubo())
    _finish_job(job_id, model_path)


# ── Utilidades de imagen ──────────────────────────────────────────────────────

def _preprocess_images(job_dir: Path) -> List[Path]:
    from PIL import Image
    src = job_dir / "images"
    dst = job_dir / "processed"
    dst.mkdir(exist_ok=True)
    valid: List[Path] = []
    for i, p in enumerate(sorted(src.glob("*"))):
        try:
            with Image.open(p) as img:
                img = img.convert("RGB")
                img.thumbnail((2000, 2000), Image.LANCZOS)
                clean = Image.new("RGB", img.size)
                clean.putdata(list(img.getdata()))
                out = dst / f"{i:04d}.jpg"
                clean.save(out, "JPEG", quality=92)
                valid.append(out)
        except Exception as e:
            print(f"[worker] skip {p.name}: {e}")
    return valid


# ── Conversión PLY → GLB ──────────────────────────────────────────────────────

def _ply_to_glb(ply_path: Path, glb_path: Path) -> None:
    """Convierte PLY (nube de puntos o malla) a GLB."""
    import trimesh
    import numpy as np

    loaded = trimesh.load(str(ply_path))

    # Si es malla real (tiene caras), exportar directo
    if isinstance(loaded, trimesh.Trimesh) and len(loaded.faces) > 0:
        loaded.export(str(glb_path))
        return
    if hasattr(loaded, "geometry"):
        parts = [v for v in loaded.geometry.values()
                 if isinstance(v, trimesh.Trimesh) and len(v.faces) > 0]
        if parts:
            trimesh.util.concatenate(parts).export(str(glb_path))
            return

    # Es nube de puntos → reconstrucción Poisson con scipy
    pts = np.asarray(loaded.vertices if hasattr(loaded, "vertices") else list(loaded.vertices))
    if len(pts) < 50:
        raise RuntimeError(
            "Muy pocos puntos reconstruidos. "
            "Sube más fotos con mayor superposición entre ellas."
        )

    try:
        from scipy.spatial import ConvexHull, Delaunay
        # Reconstrucción Delaunay 3D: más fiel a la forma que convex hull
        tri = Delaunay(pts)
        # Extraer caras de la superficie (simplices que tienen un vecino nulo)
        neighbors = tri.neighbors
        surface_simplices = tri.simplices[np.any(neighbors == -1, axis=1)]
        mesh = trimesh.Trimesh(vertices=pts, faces=surface_simplices, process=True)
        mesh.remove_degenerate_faces()
        mesh.remove_unreferenced_vertices()
        if len(mesh.faces) > 100:
            mesh.export(str(glb_path))
            return
    except Exception:
        pass

    # Último fallback: convex hull
    trimesh.PointCloud(pts).convex_hull.export(str(glb_path))


def _mesh_ply_to_glb(ply_path: Path, glb_path: Path) -> None:
    """Convierte una malla PLY ya existente a GLB usando trimesh."""
    import trimesh
    mesh = trimesh.load(str(ply_path), force="mesh")
    if hasattr(mesh, "geometry"):
        mesh = trimesh.util.concatenate(list(mesh.geometry.values()))
    mesh.export(str(glb_path))


# ── COLMAP pipeline ───────────────────────────────────────────────────────────

def _run(cmd: List[str], timeout: int = 600, **kwargs) -> subprocess.CompletedProcess:
    full_cmd = _colmap_cmd(cmd) if cmd and cmd[0] == COLMAP_BIN else cmd
    result = subprocess.run(
        full_cmd, capture_output=True, text=True, timeout=timeout, **kwargs
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Falló: {' '.join(cmd[:2])}\n{result.stderr[-800:]}"
        )
    return result


def _process_colmap(job_id: str, job_dir: Path) -> None:
    global _USE_GPU_FLAG, _GPU_FLAG_CHECKED
    if not Path(COLMAP_BIN).exists():
        raise RuntimeError(
            f"COLMAP no encontrado en {COLMAP_BIN}. "
            "Instálalo con: brew install colmap"
        )

    if not _GPU_FLAG_CHECKED:
        _USE_GPU_FLAG = _colmap_supports_use_gpu()
        _GPU_FLAG_CHECKED = True

    gpu_off = ["--SiftExtraction.use_gpu", "0"] if _USE_GPU_FLAG else []
    match_gpu_off = ["--SiftMatching.use_gpu", "0"] if _USE_GPU_FLAG else []

    output_dir = job_dir / "output"
    db_path    = job_dir / "colmap.db"
    sparse_dir = job_dir / "sparse"
    sparse_dir.mkdir(exist_ok=True)

    # 1. Preprocesar imágenes
    set_progress(job_id, 5, "procesando", "Preprocesando imágenes…")
    validas = _preprocess_images(job_dir)
    if len(validas) < 10:
        raise RuntimeError(
            f"Solo {len(validas)} imágenes válidas; se necesitan al menos 10."
        )
    images_dir = job_dir / "processed"

    # 2. Extracción de características SIFT (alta densidad)
    set_progress(job_id, 15, "procesando", "Extrayendo características SIFT…")
    _run([
        COLMAP_BIN, "feature_extractor",
        "--database_path", str(db_path),
        "--image_path",    str(images_dir),
        "--ImageReader.single_camera", "1",
        "--SiftExtraction.num_threads", "1",
        "--SiftExtraction.max_image_size", "1500",
        "--SiftExtraction.max_num_features", "8192",
        "--SiftExtraction.peak_threshold", "0.003",
        *gpu_off,
    ], env=_COLMAP_ENV)

    # 3. Matching exhaustivo con más iteraciones
    set_progress(job_id, 30, "procesando", f"Emparejando {len(validas)} imágenes…")
    _run([
        COLMAP_BIN, "exhaustive_matcher",
        "--database_path", str(db_path),
        "--SiftMatching.num_threads", "1",
        "--SiftMatching.max_ratio", "0.85",
        "--SiftMatching.max_distance", "0.7",
        *match_gpu_off,
    ], timeout=1200, env=_COLMAP_ENV)

    # 4. Reconstrucción sparse con configuración de calidad
    set_progress(job_id, 50, "procesando", "Reconstrucción sparse (SfM)…")
    _run([
        COLMAP_BIN, "mapper",
        "--database_path", str(db_path),
        "--image_path",    str(images_dir),
        "--output_path",   str(sparse_dir),
        "--Mapper.num_threads", "1",
        "--Mapper.min_num_matches", "10",
        "--Mapper.init_min_num_inliers", "50",
        "--Mapper.ba_refine_focal_length", "1",
        "--Mapper.ba_refine_principal_point", "0",
        "--Mapper.ba_global_max_num_iterations", "30",
    ], timeout=1800, env=_COLMAP_ENV)

    # Verificar que se generó un modelo
    models = sorted(sparse_dir.iterdir())
    if not models:
        raise RuntimeError(
            "COLMAP no pudo reconstruir el modelo. "
            "Asegúrate de que las fotos tengan buena superposición (~60%) "
            "e iluminación uniforme."
        )
    # Usar el modelo con más puntos
    best_model = max(
        models,
        key=lambda p: len(list(p.glob("points3D.*"))) + len(list(p.glob("images.*")))
    )

    # 5. Exportar nube de puntos densa a PLY
    set_progress(job_id, 68, "entrenando", "Exportando nube de puntos 3D…")
    sparse_ply = job_dir / "sparse_points.ply"
    _run([
        COLMAP_BIN, "model_converter",
        "--input_path",  str(best_model),
        "--output_path", str(sparse_ply),
        "--output_type", "PLY",
    ], env=_COLMAP_ENV)

    # 6. Intentar malla Delaunay (mejor que convex hull)
    set_progress(job_id, 78, "entrenando", "Generando malla 3D (Delaunay)…")
    mesh_ply = job_dir / "mesh_delaunay.ply"

    # Probar con y sin --DelaunayMeshing.input_type (varía según versión de COLMAP)
    for extra in [["--DelaunayMeshing.input_type", "sparse"], []]:
        r = subprocess.run(
            _colmap_cmd([COLMAP_BIN, "delaunay_mesher",
                         "--input_path",  str(best_model),
                         "--output_path", str(mesh_ply),
                         *extra]),
            capture_output=True, text=True, timeout=600, env=_COLMAP_ENV
        )
        if r.returncode == 0 and mesh_ply.exists() and mesh_ply.stat().st_size > 1000:
            break
        mesh_ply.unlink(missing_ok=True)
    else:
        # Fallback: reconstrucción Poisson con scipy sobre la nube sparse
        mesh_ply = sparse_ply

    # 7. Convertir PLY → GLB
    set_progress(job_id, 90, "exportando", "Exportando a .GLB…")
    glb_path = output_dir / "modelo.glb"
    _ply_to_glb(mesh_ply, glb_path)

    _finish_job(job_id, glb_path)
    _cleanup_intermediates(job_dir)


# ── Modo REAL nerfstudio (GPU) ────────────────────────────────────────────────

def _process_nerf(job_id: str, job_dir: Path) -> None:
    output_dir = job_dir / "output"
    set_progress(job_id, 5, "procesando", "Preprocesando imágenes…")
    validas = _preprocess_images(job_dir)
    if len(validas) < 10:
        raise RuntimeError(f"Solo {len(validas)} imágenes válidas; mínimo 10.")

    set_progress(job_id, 18, "procesando", f"{len(validas)} imágenes. Calculando poses…")
    ns_data = job_dir / "ns_data"
    _run(["ns-process-data", "images",
          "--data", str(job_dir / "processed"),
          "--output-dir", str(ns_data)], timeout=600)

    set_progress(job_id, 35, "entrenando", "Entrenando Instant-NGP…")
    ns_out = job_dir / "ns_output"
    proc = subprocess.Popen(
        ["ns-train", "instant-ngp",
         "--data", str(ns_data),
         "--output-dir", str(ns_out),
         "--max-num-iterations", "5000",
         "--steps-per-save", "5000",
         "--vis", "none"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    for line in proc.stdout:
        if "Step" in line and "/" in line:
            for tok in line.split():
                if "/" in tok:
                    try:
                        cur, tot = tok.split("/")
                        pct = min(int(int(cur) / int(tot) * 48) + 35, 83)
                        set_progress(job_id, pct, "entrenando", f"Paso {cur}/{tot}…")
                    except Exception:
                        pass
                    break
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Entrenamiento NeRF falló.")

    set_progress(job_id, 85, "exportando", "Exportando malla 3D…")
    ckpts = sorted(ns_out.glob("**/nerfstudio_models/*.ckpt"))
    if not ckpts:
        raise RuntimeError("No se encontraron checkpoints.")
    config_yml = ckpts[-1].parent.parent / "config.yml"
    _run(["ns-export", "poisson",
          "--load-config", str(config_yml),
          "--output-dir", str(output_dir),
          "--target-num-faces", "200000"], timeout=300)

    set_progress(job_id, 97, "exportando", "Finalizando…")
    glb_files = list(output_dir.glob("*.glb"))
    obj_files = list(output_dir.glob("*.obj"))
    if glb_files:
        model_path = glb_files[0]
    elif obj_files:
        model_path = obj_files[0]
    else:
        raise RuntimeError("No se generó ningún archivo de modelo.")
    _finish_job(job_id, model_path)


# ── Limpieza de archivos intermedios ─────────────────────────────────────────

def _cleanup_intermediates(job_dir: Path) -> None:
    for name in ["images", "processed", "sparse", "ns_data", "ns_output"]:
        p = job_dir / name
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    for fname in ["colmap.db", "sparse_points.ply"]:
        p = job_dir / fname
        if p.exists():
            p.unlink(missing_ok=True)


# ── Finalizar trabajo ─────────────────────────────────────────────────────────

def _finish_job(job_id: str, model_path: Path) -> None:
    job = storage.get_job(job_id) or {}
    job.update({
        "progress": 100, "status": "completado",
        "message": "¡Modelo 3D generado con éxito!",
        "model_path": str(model_path),
    })
    storage.update_job(job_id, job)


# ── Punto de entrada ──────────────────────────────────────────────────────────

USE_COLMAP: bool = os.getenv("USE_COLMAP", "false").lower() in ("true", "1", "yes")


def process_job(job_id: str, job_dir: Path) -> None:
    try:
        if MOCK:
            _process_mock(job_id, job_dir)
        elif USE_COLMAP or Path(COLMAP_BIN).exists():
            _process_colmap(job_id, job_dir)
        elif shutil.which("ns-process-data"):
            _process_nerf(job_id, job_dir)
        else:
            raise RuntimeError(
                "No se encontró COLMAP ni nerfstudio en el servidor. "
                "Contacta al administrador."
            )
    except Exception as exc:
        job = storage.get_job(job_id) or {}
        job.update({
            "progress": 0, "status": "error",
            "message": str(exc), "error": str(exc),
        })
        storage.update_job(job_id, job)
        raise
