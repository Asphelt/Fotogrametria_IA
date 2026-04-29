# Fotogrametría IA — Generador de Modelos 3D

Aplicación web para generar modelos 3D a partir de fotografías usando NeRF / Gaussian Splatting.

## Stack

| Capa       | Tecnología                              |
|------------|------------------------------------------|
| Frontend   | HTML + CSS + JavaScript vanilla          |
| Backend    | FastAPI (Python) + threading             |
| IA         | nerfstudio `instant-ngp` via subprocess  |
| Visor 3D   | Three.js r128 desde CDN                  |
| Formato    | `.GLB` / `.OBJ`                          |

---

## Instalación

### 1. Requisitos del sistema

- Python 3.11+
- (Modo real) GPU NVIDIA con CUDA 11.8+ y nerfstudio instalado

### 2. Entorno virtual y dependencias

```bash
cd fotogrametria-app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Ejecutar la aplicación

### Modo MOCK (sin GPU — para desarrollo)

Simula todo el proceso y devuelve un cubo `.GLB` como resultado de prueba.

```bash
cd fotogrametria-app
MOCK=true uvicorn backend.main:app --reload --port 8000
```

Windows PowerShell:
```powershell
$env:MOCK="true"; uvicorn backend.main:app --reload --port 8000
```

Abre `http://localhost:8000` en tu navegador.

---

### Modo REAL (con GPU y nerfstudio)

#### Instalar nerfstudio

```bash
pip install nerfstudio
# Verificar instalación:
ns-train --help
```

#### Ejecutar sin MOCK

```bash
cd fotogrametria-app
uvicorn backend.main:app --port 8000
```

---

## Uso

1. Abre `http://localhost:8000`
2. Arrastra o selecciona entre 20 y 200 fotos del objeto (desde múltiples ángulos)
3. Las imágenes con borrón muestran un ícono de advertencia ⚠
4. Haz clic en **Generar modelo 3D**
5. Sigue el progreso en tiempo real (WebSocket)
6. Cuando termine, el visor 3D carga automáticamente el modelo `.GLB`
7. Descarga el modelo con el botón **Descargar .GLB**

---

## Estructura de archivos

```
fotogrametria-app/
├── static/
│   ├── index.html          ← Página principal (sirve el backend)
│   ├── css/
│   │   └── estilos.css
│   └── js/
│       ├── subida.js       ← Drag-and-drop, preview, blur detection
│       ├── progreso.js     ← WebSocket y barra de progreso
│       └── visor3d.js      ← Three.js: escena, GLTF, controles
├── backend/
│   ├── main.py             ← FastAPI: rutas y WebSocket
│   ├── worker.py           ← Lógica de procesamiento (mock + real)
│   └── almacenamiento.py   ← Gestión de trabajos en disco
├── jobs/                   ← Creado automáticamente (datos de trabajos)
├── requirements.txt
└── README.md
```

---

## API

| Método | Ruta              | Descripción                          |
|--------|-------------------|--------------------------------------|
| GET    | `/`               | Sirve index.html                     |
| GET    | `/info`           | `{"mock": true/false}`               |
| POST   | `/subir`          | Sube imágenes e inicia el trabajo    |
| GET    | `/trabajo/{id}`   | Estado y porcentaje del trabajo      |
| WS     | `/ws/{id}`        | Actualizaciones en tiempo real       |
| GET    | `/modelo/{id}`    | Descarga el archivo `.GLB` generado  |
| GET    | `/trabajos`       | Lista todos los trabajos             |

---

## Requisitos de fotografía

Para obtener buenos resultados con nerfstudio:

- **Mínimo 20 fotos**, recomendado 60–150
- Iluminación uniforme, sin sombras duras
- Superposición del 60–80% entre fotos consecutivas
- Objeto completamente visible, sin partes recortadas
- Fondo simple o neutro
- Sin movimiento del objeto entre tomas

---

## Errores comunes

| Error                        | Causa                          | Solución                              |
|------------------------------|--------------------------------|---------------------------------------|
| "Mínimo 20 imágenes"         | Pocas fotos subidas            | Sube más fotografías                  |
| "ns-process-data no encontrado" | nerfstudio no instalado     | `pip install nerfstudio`              |
| "CUDA out of memory"         | GPU con poca VRAM              | Reducir resolución o usar menos fotos |
| "No checkpoints found"       | Entrenamiento interrumpido     | Revisar logs, reintentar              |

Para desarrollo sin GPU, siempre usa `MOCK=true`.
