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
    </div>
  `;
}

function filaEsqueleto() {
  return `
    <div class="dashboard-entrega-item">
      <div style="flex:1">
        <div class="ds-skeleton ds-skeleton-title"></div>
        <div class="ds-skeleton ds-skeleton-line"></div>
      </div>
    </div>
  `;
}

document.getElementById('cursando-grid').innerHTML = tarjetaEsqueleto().repeat(3);
document.getElementById('entregas-list').innerHTML = filaEsqueleto().repeat(3);

// --- Cabecera: saludo según la hora del día ---

function mostrarSaludo() {
  const hora = new Date().getHours();
  let saludo;
  if (hora < 6) saludo = 'Buenas noches';
  else if (hora < 12) saludo = 'Buenos días';
  else if (hora < 20) saludo = 'Buenas tardes';
  else saludo = 'Buenas noches';
  document.getElementById('saludo').textContent = saludo;
}

// --- Tarjeta principal: progreso del grado + Asignaturas cursándose ---

function renderCursando(asignaturas) {
  const grid = document.getElementById('cursando-grid');
  const cursando = asignaturas.filter((a) => a.estado === 'cursando');

  if (cursando.length === 0) {
    grid.innerHTML = `
      <div class="ds-empty-state" style="grid-column: 1 / -1">
        <div class="ds-empty-state-icon">📚</div>
        <div class="ds-empty-state-title">Ninguna asignatura en curso</div>
        <p class="ds-empty-state-description">Cuando elijas o empieces una asignatura, aparecerá aquí.</p>
      </div>
    `;
    reanimar(grid);
    return;
  }

  grid.innerHTML = cursando.map((a) => `
    <a class="ds-card ds-card--interactive dashboard-asignatura-card" href="/vista/asignaturas/${a.id}">
      <p class="ds-h3">${a.siglas ? `${escapeHtml(a.siglas)} · ` : ''}${escapeHtml(a.nombre)}</p>
      <p class="ds-caption" style="margin-top:4px">${a.creditos_ects} ECTS · ${a.tipo === 'optativa' ? 'Optativa' : 'Obligatoria'}</p>
    </a>
  `).join('');
  reanimar(grid);
}

// Carga total fija del grado (spec: 240 ECTS = formación básica + obligatoria + TFG +
// optativas/prácticas). No se calcula desde la BD porque es un dato del plan de
// estudios, no algo que dependa de qué asignaturas haya cargadas.
const TOTAL_GRADO_ECTS = 240;
const NOMBRE_TFG = 'Trabajo de Fin de Grado';

function actualizarDesglose(clave, aprobados, total) {
  const porcentaje = total > 0 ? Math.min((aprobados / total) * 100, 100) : 0;
  document.getElementById(`desglose-${clave}-texto`).textContent = `${aprobados} / ${total} ECTS`;
  document.getElementById(`desglose-${clave}-barra`).style.width = `${porcentaje}%`;
}

function renderProgreso(asignaturas) {
  const esTFG = (a) => a.nombre === NOMBRE_TFG;
  const obligatorias = asignaturas.filter((a) => a.tipo === 'obligatoria' && !esTFG(a));
  const tfg = asignaturas.filter(esTFG);
  // Del catálogo de optativas solo cuentan las que ya se han elegido (no_elegida
  // queda fuera, igual que en el resto de la app): son las únicas "en curso" de verdad.
  const optativasElegidas = asignaturas.filter((a) => a.tipo === 'optativa' && a.estado !== 'no_elegida');

  const totalObligatorias = obligatorias.reduce((s, a) => s + a.creditos_ects, 0);
  const totalTFG = tfg.reduce((s, a) => s + a.creditos_ects, 0);
  // Las optativas son la única categoría con margen de elección: su total "objetivo"
  // es lo que falta hasta los 240 ECTS una vez fijadas las obligatorias y el TFG,
  // no una cifra fija — así cuadra siempre con el total del grado.
  const totalOptativas = Math.max(TOTAL_GRADO_ECTS - totalObligatorias - totalTFG, 0);

  const sumaSuperadas = (lista) => lista.filter((a) => a.estado === 'superada').reduce((s, a) => s + a.creditos_ects, 0);
  const aprobadosObligatorias = sumaSuperadas(obligatorias);
  const aprobadosTFG = sumaSuperadas(tfg);
  const aprobadosOptativas = sumaSuperadas(optativasElegidas);
  const totalAprobados = aprobadosObligatorias + aprobadosTFG + aprobadosOptativas;

  document.getElementById('progreso-creditos').textContent = `${totalAprobados}`;
  document.getElementById('progreso-total').textContent = `de ${TOTAL_GRADO_ECTS} ECTS aprobados`;
  document.getElementById('progreso-barra').style.width = `${(totalAprobados / TOTAL_GRADO_ECTS) * 100}%`;

  actualizarDesglose('obligatorias', aprobadosObligatorias, totalObligatorias);
  actualizarDesglose('optativas', aprobadosOptativas, totalOptativas);
  actualizarDesglose('tfg', aprobadosTFG, totalTFG);
}

async function cargarAsignaturas() {
  const asignaturas = await api('/asignaturas');
  renderProgreso(asignaturas);
  renderCursando(asignaturas);
}

// --- Próximas entregas ---

function calcularCountdown(fechaIso) {
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const fecha = new Date(fechaIso + 'T00:00:00');
  const dias = Math.round((fecha - hoy) / 86400000);

  let nivel;
  if (dias < 3) nivel = 'rojo';
  else if (dias < 7) nivel = 'naranja';
  else nivel = 'gris';

  let texto;
  if (dias < 0) texto = `Atrasada ${-dias} día${-dias !== 1 ? 's' : ''}`;
  else if (dias === 0) texto = 'Hoy';
  else texto = `Faltan ${dias} día${dias !== 1 ? 's' : ''}`;

  return { nivel, texto };
}

const ETIQUETA_TIPO_TAREA = {
  examen: 'Examen',
  entrega: 'Entrega',
  tarea_general: 'Tarea',
  tutoria: 'Tutoría',
};

const BADGE_POR_NIVEL = {
  rojo: 'ds-badge-danger',
  naranja: 'ds-badge-warning',
  gris: 'ds-badge',
};

function renderEntregas(tareas) {
  const lista = document.getElementById('entregas-list');
  const proximas = [...tareas].sort((a, b) => a.fecha.localeCompare(b.fecha)).slice(0, 6);

  if (proximas.length === 0) {
    lista.innerHTML = `
      <div class="ds-empty-state">
        <div class="ds-empty-state-icon">🗓️</div>
        <div class="ds-empty-state-title">Sin próximas entregas</div>
        <p class="ds-empty-state-description">Los exámenes, entregas y tareas pendientes aparecerán aquí.</p>
      </div>
    `;
    reanimar(lista);
    return;
  }

  lista.innerHTML = proximas.map((t) => {
    const { nivel, texto } = calcularCountdown(t.fecha);
    // Integración con el visor PDF (spec V2.2_VISOR_PDF): si el examen/tarea tiene un
    // documento vinculado, abrir directamente ese PDF en vez de solo la asignatura.
    const url = (t.documento_id && t.asignatura_id)
      ? `/vista/asignaturas/${t.asignatura_id}?doc=${t.documento_id}`
      : t.asignatura_id
        ? `/vista/asignaturas/${t.asignatura_id}`
        : `/vista/calendario?anio=${t.fecha.slice(0, 4)}&mes=${parseInt(t.fecha.slice(5, 7), 10)}`;
    const asignaturaTxt = t.asignatura_nombre
      ? `<span class="ds-caption">${escapeHtml(t.asignatura_nombre)}</span>` : '';

    return `
      <li class="dashboard-entrega-item">
        <a class="dashboard-entrega-link" href="${url}">
          <span class="dashboard-entrega-titulo">${escapeHtml(t.titulo)}</span>
          ${asignaturaTxt}
        </a>
        <span class="dashboard-entrega-badges">
          ${t.documento_id ? '<span class="ds-badge" title="Tiene un PDF vinculado">📄</span>' : ''}
          <span class="ds-badge">${ETIQUETA_TIPO_TAREA[t.tipo] || 'Tarea'}</span>
          <span class="ds-badge ${BADGE_POR_NIVEL[nivel]}">${texto}</span>
        </span>
      </li>
    `;
  }).join('');
  reanimar(lista);
}

async function cargarEntregas() {
  const tareas = await api('/tareas?completada=false');
  renderEntregas(tareas);
}

// --- "Continúa donde lo dejaste" (spec Continua_donde_lo_dejaste, punto 3) ---

function tiempoRelativo(fechaIso) {
  // El backend serializa datetimes naive en UTC (sin sufijo Z): hay que añadirlo
  // explícitamente o el navegador los interpreta como hora local y el cálculo
  // queda desfasado por el huso horario del usuario.
  const iso = /Z$|[+-]\d{2}:\d{2}$/.test(fechaIso) ? fechaIso : `${fechaIso}Z`;
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutos = Math.round(diffMs / 60000);
  if (minutos < 1) return 'Ahora mismo';
  if (minutos < 60) return `Hace ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `Hace ${horas} h`;
  const dias = Math.round(horas / 24);
  return `Hace ${dias} día${dias !== 1 ? 's' : ''}`;
}

function renderContinuar(documentos) {
  const seccion = document.getElementById('seccion-continuar');
  const lista = document.getElementById('continuar-grid');
  if (!documentos || documentos.length === 0) {
    seccion.style.display = 'none';
    return;
  }
  seccion.style.display = '';
  lista.innerHTML = documentos.map((d) => {
    const url = `/vista/asignaturas/${d.asignatura_id}?doc=${d.id}&pagina=${d.ultima_pagina_vista || 1}`;
    const paginaTxt = d.total_paginas ? `Página ${d.ultima_pagina_vista || 1} de ${d.total_paginas}` : `Página ${d.ultima_pagina_vista || 1}`;
    const porcentaje = Math.round((d.porcentaje_leido || 0) * 100);
    return `
      <a class="ds-card ds-card--interactive dashboard-continuar-card" href="${url}" data-id="${d.id}">
        <button type="button" class="dashboard-continuar-btn-quitar" data-tooltip="Quitar de la lista" aria-label="Quitar de la lista">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
        </button>
        <p class="ds-h3" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:24px">${escapeHtml(d.nombre_archivo)}</p>
        <p class="ds-caption" style="margin-top:4px">${paginaTxt} · ${tiempoRelativo(d.fecha_ultima_apertura)}</p>
        <div class="ds-progress dashboard-progreso-mini" style="margin-top:8px">
          <div class="ds-progress-bar" style="width:${porcentaje}%"></div>
        </div>
      </a>
    `;
  }).join('');
  reanimar(lista);

  lista.querySelectorAll('.dashboard-continuar-btn-quitar').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const tarjeta = btn.closest('.dashboard-continuar-card');
      const id = tarjeta.dataset.id;
      try {
        await api(`/documentos/${id}/quitar-continuar`, { method: 'POST' });
        await cargarContinuar();
        mostrarToast('Quitado de "Continúa donde lo dejaste"', 'success');
      } catch (err) {
        mostrarToast('Error al quitar: ' + err.message, 'danger');
      }
    });
  });
}

async function cargarContinuar() {
  try {
    const documentos = await api('/documentos/recientes?limite=3');
    renderContinuar(documentos);
  } catch (err) {
    document.getElementById('seccion-continuar').style.display = 'none';
  }
}

function formatoNota(nota) {
  return nota.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
}

async function cargarMediaCurso() {
  try {
    const resumen = await api('/asignaturas/media-curso');
    document.getElementById('media-curso-valor').textContent =
      resumen.media_general != null ? formatoNota(resumen.media_general) : '—';
    document.getElementById('media-curso-total').textContent = resumen.total;
    document.getElementById('media-curso-aprobadas').textContent = resumen.aprobadas;
    document.getElementById('media-curso-suspendidas').textContent = resumen.suspendidas;
    document.getElementById('media-curso-pendientes').textContent = resumen.pendientes_evaluar;
    document.getElementById('media-curso-nota-alta').textContent =
      resumen.nota_mas_alta != null ? formatoNota(resumen.nota_mas_alta) : '—';
    document.getElementById('media-curso-nota-baja').textContent =
      resumen.nota_mas_baja != null ? formatoNota(resumen.nota_mas_baja) : '—';
  } catch (err) {
    mostrarToast('Error al cargar la media del curso: ' + err.message, 'danger');
  }
}

// --- Repaso pendiente hoy + Hitos (spec "qué se puede mejorar": ambas existían en el
// backend pero sin ningún acceso desde la UI; este widget las hace visibles) ---

async function cargarRepasoHoy() {
  try {
    const conceptos = await api('/repaso-hoy');
    document.getElementById('repaso-hoy-count').textContent = conceptos.length;
  } catch (err) {
    document.getElementById('repaso-hoy-count').textContent = '—';
  }
}

const ETIQUETA_ESTADO_HITO = { pendiente: '⚪', en_progreso: '🟡', hecho: '🟢' };
const SIGUIENTE_ESTADO_HITO = { pendiente: 'en_progreso', en_progreso: 'hecho', hecho: 'pendiente' };

let HITOS = [];

function renderHitos() {
  const lista = document.getElementById('hitos-list');
  if (HITOS.length === 0) {
    lista.innerHTML = '<li class="dashboard-hito-vacio ds-caption ds-text-secondary">Sin hitos todavía.</li>';
    return;
  }
  lista.innerHTML = HITOS.map((h) => `
    <li class="dashboard-hito-item${h.estado === 'hecho' ? ' completado' : ''}" data-id="${h.id}">
      <button type="button" class="dashboard-hito-estado" title="Cambiar estado (${h.estado})">${ETIQUETA_ESTADO_HITO[h.estado]}</button>
      <span class="dashboard-hito-nombre">${escapeHtml(h.nombre)}</span>
      <button type="button" class="dashboard-hito-borrar" aria-label="Borrar hito">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
      </button>
    </li>
  `).join('');

  lista.querySelectorAll('.dashboard-hito-estado').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.closest('.dashboard-hito-item').dataset.id);
      const hito = HITOS.find((h) => h.id === id);
      await api(`/hitos/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ estado: SIGUIENTE_ESTADO_HITO[hito.estado] }),
      });
      await cargarHitos();
    });
  });
  lista.querySelectorAll('.dashboard-hito-borrar').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.closest('.dashboard-hito-item').dataset.id;
      await api(`/hitos/${id}`, { method: 'DELETE' });
      await cargarHitos();
    });
  });
}

async function cargarHitos() {
  HITOS = await api('/hitos');
  renderHitos();
}

document.getElementById('form-nuevo-hito').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('nuevo-hito-nombre');
  const nombre = input.value.trim();
  if (!nombre) return;
  await api('/hitos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nombre }),
  });
  input.value = '';
  await cargarHitos();
});

mostrarSaludo();
cargarAsignaturas();
cargarEntregas();
cargarContinuar();
cargarMediaCurso();
cargarRepasoHoy();
cargarHitos();
