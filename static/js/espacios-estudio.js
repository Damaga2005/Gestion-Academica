async function api(path, options = {}) {
  const metodo = (options.method || 'GET').toUpperCase();
  if (metodo !== 'GET' && metodo !== 'HEAD') {
    const meta = document.querySelector('meta[name="csrf-token"]');
    options.headers = Object.assign({}, options.headers, { 'X-CSRFToken': meta ? meta.content : '' });
  }
  const res = await fetch(path, options);
  if (!res.ok) {
    let mensaje = `Error ${res.status}`;
    try {
      const data = await res.json();
      mensaje = data.error || mensaje;
    } catch (e) { /* respuesta sin cuerpo JSON */ }
    throw new Error(mensaje);
  }
  if (res.status === 204) return null;
  return res.json();
}

function escapeHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto == null ? '' : texto;
  return div.innerHTML;
}

function tarjetaEsqueleto() {
  return `
    <div class="ds-card">
      <div class="ds-skeleton ds-skeleton-title"></div>
      <div class="ds-skeleton ds-skeleton-line"></div>
      <div class="ds-skeleton ds-skeleton-bar"></div>
    </div>
  `;
}
document.getElementById('espacios-grid').innerHTML = tarjetaEsqueleto().repeat(3);

function textoCuentaAtras(dias) {
  if (dias < 0) return `Hace ${-dias} día${-dias !== 1 ? 's' : ''}`;
  if (dias === 0) return 'Es hoy';
  return `Faltan ${dias} día${dias !== 1 ? 's' : ''}`;
}

function renderEspacios(espacios) {
  const grid = document.getElementById('espacios-grid');

  if (espacios.length === 0) {
    const filtrando = typeof filtroActivo !== 'undefined' && filtroActivo !== 'todos';
    grid.innerHTML = `
      <div class="ds-empty-state" style="grid-column: 1 / -1">
        <div class="ds-empty-state-icon">📚</div>
        <div class="ds-empty-state-title">${filtrando ? 'Ningún espacio con este filtro' : 'Sin espacios de estudio todavía'}</div>
        <p class="ds-empty-state-description">${filtrando ? 'Prueba con otro filtro.' : 'Créalos marcando "Crear Espacio de Estudio automáticamente" al guardar un examen o entrega en el Calendario.'}</p>
      </div>
    `;
    reanimar(grid);
    return;
  }

  grid.innerHTML = espacios.map((e) => {
    const urgente = e.dias_restantes !== null && e.dias_restantes <= 3;
    // Mismo umbral que "espacio_sin_empezar" en routes/notificaciones.py.
    const sinEmpezar = urgente && e.dias_restantes >= 0 && e.total_documentos > 0 && e.progreso_pct === 0;
    return `
      <a class="ds-card ds-card--interactive espacio-card" href="/vista/espacios-estudio/${e.id}">
        <div class="espacio-card-header">
          <p class="ds-h3">${escapeHtml(e.nombre)}</p>
          ${sinEmpezar ? '<span class="ds-badge ds-badge-danger">Sin empezar</span>' : ''}
          ${e.asignatura_siglas ? `<span class="ds-badge ds-badge-accent">${escapeHtml(e.asignatura_siglas)}</span>` : ''}
        </div>
        <p class="ds-caption">${e.asignatura_nombre ? escapeHtml(e.asignatura_nombre) : 'Sin asignatura'}${e.fecha ? ' · ' + new Date(e.fecha + 'T00:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'long' }) : ''}</p>
        <div class="espacio-card-cuenta-atras">
          ${urgente ? '<span>⚠</span>' : '<span>📅</span>'}
          <span class="espacio-card-dias ${urgente ? 'ds-text-danger' : ''}">${e.dias_restantes !== null ? textoCuentaAtras(e.dias_restantes) : ''}</span>
        </div>
        <div class="espacio-card-progreso">
          <div class="espacio-card-progreso-texto">
            <span class="ds-caption">${e.documentos_leidos}/${e.total_documentos} documentos leídos</span>
            <span class="ds-caption">${e.progreso_pct}%</span>
          </div>
          <div class="ds-progress"><div class="ds-progress-bar" style="width:${e.progreso_pct}%"></div></div>
        </div>
      </a>
    `;
  }).join('');
  reanimar(grid);
}

let espaciosCache = [];
let filtroActivo = 'todos';

function aplicarFiltro() {
  const filtrados = espaciosCache.filter((e) => {
    if (filtroActivo === 'sin_empezar') return e.total_documentos > 0 && e.progreso_pct === 0;
    if (filtroActivo === 'en_progreso') return e.progreso_pct > 0 && e.progreso_pct < 100;
    if (filtroActivo === 'completados') return e.total_documentos > 0 && e.progreso_pct === 100;
    return true;
  });
  renderEspacios(filtrados);
}

async function cargarEspacios() {
  try {
    espaciosCache = await api('/espacios-estudio');
    aplicarFiltro();
  } catch (err) {
    mostrarToast('Error al cargar espacios de estudio: ' + err.message, 'danger');
  }
}

document.getElementById('espacios-filtros').addEventListener('click', (e) => {
  const boton = e.target.closest('.filtro-chip');
  if (!boton) return;
  document.querySelectorAll('#espacios-filtros .filtro-chip').forEach((b) => b.classList.remove('is-active'));
  boton.classList.add('is-active');
  filtroActivo = boton.dataset.filtro;
  aplicarFiltro();
});

cargarEspacios();
