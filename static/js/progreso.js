/* ── WebSocket de progreso ── */
let ws = null;
let wsReconectar = null;

/* Mapa de rango de progreso → step activo */
const STEPS_MAP = [
  { step: 'validar',        min: 0,  max: 14 },
  { step: 'preprocesar',    min: 15, max: 24 },
  { step: 'caracteristicas',min: 25, max: 34 },
  { step: 'entrenando',     min: 35, max: 84 },
  { step: 'exportando',     min: 85, max: 99 },
  { step: 'completado',     min: 100,max: 100 },
];

function conectarWebSocket(jobId) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${location.host}/ws/${jobId}`;

  ws = new WebSocket(url);

  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      actualizarProgreso(data);
    } catch (_) {}
  };

  ws.onerror = () => {
    /* reconectar via polling como fallback */
    ws.close();
  };

  ws.onclose = () => {
    if (!['completado', 'error'].includes(ws._lastStatus)) {
      wsReconectar = setTimeout(() => pollFallback(jobId), 2000);
    }
  };

  ws._lastStatus = '';
}

async function pollFallback(jobId) {
  try {
    const r = await fetch(`/trabajo/${jobId}`);
    const data = await r.json();
    actualizarProgreso(data);
    if (!['completado', 'error'].includes(data.status)) {
      wsReconectar = setTimeout(() => pollFallback(jobId), 1500);
    }
  } catch (_) {}
}

function actualizarProgreso(data) {
  if (ws) ws._lastStatus = data.status;

  const pct = data.progress || 0;
  const fill = document.getElementById('progress-fill');
  const pctEl = document.getElementById('progress-pct');
  const msgEl = document.getElementById('progress-msg');
  const titulo = document.getElementById('prog-titulo');

  fill.style.width = pct + '%';
  pctEl.textContent = pct + '%';
  msgEl.textContent = data.message || '…';

  /* Resaltar step activo */
  STEPS_MAP.forEach(({ step, min, max }) => {
    const el = document.querySelector(`.step[data-step="${step}"]`);
    if (!el) return;
    el.classList.remove('active', 'done');
    if (pct >= min && pct <= max && data.status !== 'error') {
      el.classList.add('active');
      actualizarIconoStep(el, 'active');
    } else if (pct > max) {
      el.classList.add('done');
      actualizarIconoStep(el, 'done');
    } else {
      actualizarIconoStep(el, 'pending');
    }
  });

  /* Terminado con éxito */
  if (data.status === 'completado') {
    fill.classList.add('done');
    fill.classList.remove('error');
    titulo.textContent = '¡Modelo 3D generado!';
    document.getElementById('prog-subtitulo').textContent = data.message || '';
    clearTimeout(wsReconectar);

    setTimeout(() => {
      ocultarSeccion('sec-progreso');
      mostrarSeccion('sec-visor');
      initVisor();
      cargarModelo(data.id);
      cargarHistorial();
    }, 800);
  }

  /* Error */
  if (data.status === 'error') {
    fill.classList.add('error');
    fill.classList.remove('done');
    titulo.textContent = 'Procesamiento fallido';
    clearTimeout(wsReconectar);

    const errCard = document.getElementById('error-card');
    errCard.classList.remove('hidden');
    document.getElementById('error-msg').textContent = data.error || data.message || 'Error desconocido';
  }
}

function actualizarIconoStep(el, estado) {
  const svg = el.querySelector('.step-icon svg');
  if (!svg) return;

  if (estado === 'done') {
    svg.innerHTML = '<path d="M3 8l3 3 7-7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>';
  } else if (estado === 'active') {
    svg.innerHTML = '<circle cx="8" cy="8" r="3" fill="currentColor"/><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" fill="none"/>';
  } else {
    svg.innerHTML = '<circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" fill="none"/>';
  }
}

/* Exponer helpers de sección para subida.js */
function mostrarSeccion(id) { document.getElementById(id).classList.remove('hidden'); }
function ocultarSeccion(id) { document.getElementById(id).classList.add('hidden'); }
