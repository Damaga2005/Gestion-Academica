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
    const url = t.asignatura_id
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

mostrarSaludo();
cargarAsignaturas();
cargarEntregas();
