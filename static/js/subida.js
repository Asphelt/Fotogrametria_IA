/* ── Estado global ── */
let archivosSeleccionados = [];
let trabajoActualId = null;

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  setupDragAndDrop();
  setupFileInput();
  cargarHistorial();
  checkMockMode();
});

function checkMockMode() {
  fetch('/info').then(r => r.json()).then(d => {
    if (d.mock) {
      document.getElementById('mock-badge').style.display = 'flex';
    }
  }).catch(() => {});
}

/* ── Drag & Drop ── */
function setupDragAndDrop() {
  const zone = document.getElementById('drop-zone');

  zone.addEventListener('click', (e) => {
    if (e.target.closest('button')) return;
    document.getElementById('file-input').click();
  });

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('dragover');
  });

  zone.addEventListener('dragleave', (e) => {
    if (!zone.contains(e.relatedTarget)) {
      zone.classList.remove('dragover');
    }
  });

  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('dragover');
    const files = [...e.dataTransfer.files].filter(f => f.type.startsWith('image/'));
    agregarArchivos(files);
  });
}

function setupFileInput() {
  document.getElementById('file-input').addEventListener('change', (e) => {
    agregarArchivos([...e.target.files]);
    e.target.value = '';
  });
}

/* ── Gestión de archivos ── */
function agregarArchivos(nuevos) {
  const formatos = ['image/jpeg','image/png','image/webp','image/bmp','image/tiff'];
  const validos = nuevos.filter(f => formatos.includes(f.type));
  const invalidos = nuevos.length - validos.length;

  if (invalidos > 0) {
    mostrarToast(`${invalidos} archivo(s) ignorado(s) — formato no soportado`, 'warn');
  }

  const disponibles = 200 - archivosSeleccionados.length;
  const aTomar = validos.slice(0, disponibles);

  if (validos.length > disponibles) {
    mostrarToast(`Solo se añadieron ${aTomar.length} imágenes (límite 200)`, 'warn');
  }

  aTomar.forEach(f => {
    archivosSeleccionados.push(f);
    renderThumb(f, archivosSeleccionados.length - 1);
  });

  actualizarBarraSubida();
}

function limpiarSeleccion() {
  archivosSeleccionados = [];
  document.getElementById('image-grid').innerHTML = '';
  actualizarBarraSubida();
}

/* ── Thumbnail con detección de borrosidad ── */
function renderThumb(file, idx) {
  const grid = document.getElementById('image-grid');
  const thumb = document.createElement('div');
  thumb.className = 'img-thumb';
  thumb.dataset.idx = idx;

  const img = document.createElement('img');
  img.alt = file.name;
  thumb.appendChild(img);

  const badge = document.createElement('div');
  badge.className = 'img-badge';
  thumb.appendChild(badge);

  const remove = document.createElement('div');
  remove.className = 'img-remove';
  remove.innerHTML = '&times;';
  remove.addEventListener('click', (e) => {
    e.stopPropagation();
    eliminarArchivo(idx);
  });
  thumb.appendChild(remove);

  grid.appendChild(thumb);

  const reader = new FileReader();
  reader.onload = (e) => {
    img.src = e.target.result;
    img.onload = () => {
      const esNitida = detectarNitidez(img);
      badge.classList.add(esNitida ? 'ok' : 'warn');
      badge.title = esNitida ? 'Imagen nítida' : 'Posible imagen borrosa';
      badge.innerHTML = esNitida
        ? '<svg viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        : '<svg viewBox="0 0 12 12" fill="none"><path d="M6 4v3M6 8.5v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
      actualizarConteoCalidad();
    };
  };
  reader.readAsDataURL(file);
}

function eliminarArchivo(idx) {
  archivosSeleccionados.splice(idx, 1);
  const grid = document.getElementById('image-grid');
  grid.innerHTML = '';
  archivosSeleccionados.forEach((f, i) => renderThumb(f, i));
  actualizarBarraSubida();
}

/* ── Detección de borrosidad (varianza del Laplaciano) ── */
function detectarNitidez(img) {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size; canvas.height = size;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0, size, size);
  const { data } = ctx.getImageData(0, 0, size, size);

  const gray = new Float32Array(size * size);
  for (let i = 0; i < data.length; i += 4) {
    gray[i / 4] = 0.299 * data[i] + 0.587 * data[i+1] + 0.114 * data[i+2];
  }

  let suma = 0, n = 0;
  for (let y = 1; y < size - 1; y++) {
    for (let x = 1; x < size - 1; x++) {
      const i = y * size + x;
      const lap = gray[i-size] + gray[i+size] + gray[i-1] + gray[i+1] - 4 * gray[i];
      suma += lap * lap;
      n++;
    }
  }
  return (suma / n) > 80;
}

/* ── UI helpers ── */
function actualizarConteoCalidad() {
  const borrosas = document.querySelectorAll('.img-badge.warn').length;
  const qEl = document.getElementById('quality-text');
  if (borrosas > 0) {
    qEl.textContent = `⚠ ${borrosas} imagen(s) posiblemente borrosa(s)`;
    qEl.className = 'quality-warn';
  } else {
    qEl.textContent = '';
  }
}

function actualizarBarraSubida() {
  const n = archivosSeleccionados.length;
  const bar = document.getElementById('upload-bar');
  const btn = document.getElementById('btn-procesar');

  document.getElementById('count-text').textContent =
    `${n} imagen${n !== 1 ? 'es' : ''} seleccionada${n !== 1 ? 's' : ''}`;

  bar.style.display = n > 0 ? 'flex' : 'none';
  btn.disabled = n < 10;

  if (n > 0 && n < 10) {
    document.getElementById('count-text').textContent += ` (mínimo 10)`;
  }

  actualizarConteoCalidad();
}

/* ── Iniciar procesamiento ── */
async function iniciarProcesamiento() {
  const btn = document.getElementById('btn-procesar');
  btn.disabled = true;
  btn.textContent = 'Subiendo…';

  const formData = new FormData();
  archivosSeleccionados.forEach(f => formData.append('imagenes', f));

  try {
    const resp = await fetch('/subir', { method: 'POST', body: formData });
    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.detail || 'Error al subir imágenes');
    }

    trabajoActualId = data.job_id;
    mostrarSeccion('sec-progreso');
    ocultarSeccion('sec-subida');
    conectarWebSocket(data.job_id);
    window.scrollTo({ top: 0, behavior: 'smooth' });

  } catch (err) {
    mostrarToast(err.message, 'error');
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 8L6 12L14 4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg> Generar modelo 3D`;
  }
}

/* ── Nuevo trabajo ── */
function nuevoTrabajo() {
  trabajoActualId = null;
  archivosSeleccionados = [];
  document.getElementById('image-grid').innerHTML = '';

  ocultarSeccion('sec-progreso');
  ocultarSeccion('sec-visor');
  mostrarSeccion('sec-subida');
  actualizarBarraSubida();
  cargarHistorial();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ── Historial ── */
async function cargarHistorial() {
  try {
    const resp = await fetch('/trabajos');
    const trabajos = await resp.json();
    renderHistorial(trabajos);
  } catch (_) {}
}

function renderHistorial(trabajos) {
  const lista = document.getElementById('historial-lista');

  if (!trabajos.length) {
    lista.innerHTML = '<p class="empty-msg">Aún no hay trabajos anteriores</p>';
    return;
  }

  lista.innerHTML = trabajos.slice(0, 20).map(t => {
    const fecha = t.created_at
      ? new Date(t.created_at).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' })
      : '—';
    const imgCount = t.image_count || '?';
    const descarga = t.status === 'completado'
      ? `<a href="/modelo/${t.id}" download class="btn-icon" title="Descargar .GLB">
           <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1v8M4 7l3 2 3-2M1 11h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
         </a>`
      : '';

    return `
      <div class="historial-item">
        <span class="hist-status ${t.status}"></span>
        <div class="hist-info">
          <div class="hist-id">${t.id.slice(0, 8)}…</div>
          <div class="hist-meta">${fecha} · ${imgCount} imágenes</div>
        </div>
        <span class="hist-badge ${t.status}">${tradStatus(t.status)}</span>
        <div class="hist-actions">${descarga}</div>
      </div>`;
  }).join('');
}

function tradStatus(s) {
  return { completado: 'Listo', error: 'Error', procesando: 'Procesando',
           entrenando: 'Entrenando', exportando: 'Exportando', en_cola: 'En cola' }[s] || s;
}

/* ── Helpers UI ── */
function mostrarSeccion(id) { document.getElementById(id).classList.remove('hidden'); }
function ocultarSeccion(id) { document.getElementById(id).classList.add('hidden'); }

function mostrarToast(msg, tipo = 'info') {
  const t = document.createElement('div');
  t.style.cssText = `
    position:fixed; bottom:24px; left:50%; transform:translateX(-50%);
    background:${tipo === 'error' ? '#3a0f0f' : tipo === 'warn' ? '#3a2400' : '#1f3a5f'};
    border:1px solid ${tipo === 'error' ? '#f85149' : tipo === 'warn' ? '#f0883e' : '#58a6ff'};
    color:#e6edf3; padding:10px 20px; border-radius:8px; font-size:.875rem;
    z-index:9999; max-width:90vw; text-align:center; pointer-events:none;
  `;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}
