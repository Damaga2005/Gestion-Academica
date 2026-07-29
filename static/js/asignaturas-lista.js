async function api(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

function escapeHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto == null ? '' : texto;
  return div.innerHTML;
}

function calcularCountdown(fechaIso) {
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const fecha = new Date(fechaIso + 'T00:00:00');
  const dias = Math.round((fecha - hoy) / 86400000);

  if (dias < 0) return `Atrasada ${-dias} día${-dias !== 1 ? 's' : ''}`;
  if (dias === 0) return 'Hoy';
  return `Faltan ${dias} día${dias !== 1 ? 's' : ''}`;
}

const ETIQUETA_ESTADO = {
  superada: 'Superada',
  cursando: 'Cursando',
  pendiente: 'Pendiente',
  no_superada: 'No superada',
};

const BADGE_POR_ESTADO = {
  superada: 'ds-badge-success',
  cursando: 'ds-badge-accent',
  pendiente: 'ds-badge',
  no_superada: 'ds-badge-danger',
};

// "Estado de las Asignaturas" (spec): indicador calculado solo a partir de las
// notas (ver calcular_estado_notas en el backend), independiente del estado
// manual de arriba.
const TIPOS_TAREA_EXAMEN = ['examen', 'examen_parcial', 'examen_final', 'recuperacion'];
const ETIQUETA_ESTADO_NOTAS = {
  aprobada: '🟢 Aprobada',
  en_progreso: '🟡 En progreso',
  suspendida: '🔴 Suspendida',
  sin_evaluar: '⚪ Sin evaluar',
};
const BADGE_POR_ESTADO_NOTAS = {
  aprobada: 'ds-badge-success',
  en_progreso: 'ds-badge-warning',
  suspendida: 'ds-badge-danger',
  sin_evaluar: 'ds-badge-outline',
};

function formatoNota(nota) {
  return nota.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
}

let TODAS_ASIGNATURAS = [];
let OPTATIVAS_POR_ELEGIR = [];
let PROXIMA_ENTREGA_POR_ASIGNATURA = {};
let PROXIMA_EVALUACION_POR_ASIGNATURA = {};
let cargaInicial = true;

function tarjetaEsqueleto() {
  return `
    <div class="ds-card">
      <div class="ds-skeleton ds-skeleton-title"></div>
      <div class="ds-skeleton ds-skeleton-line"></div>
      <div class="ds-skeleton ds-skeleton-bar"></div>
    </div>
  `;
}
document.getElementById('asignaturas-grid').innerHTML = tarjetaEsqueleto().repeat(6);

let filtroEstado = layoutState.get('asignaturas-filtro-estado', 'todas');
let filtroTipo = layoutState.get('asignaturas-filtro-tipo', 'todos');
let filtroCurso = layoutState.get('asignaturas-filtro-curso', 'todos');
let terminoBusqueda = layoutState.get('asignaturas-busqueda', '');
let ordenActual = layoutState.get('asignaturas-orden', 'curso');

document.querySelectorAll('#filtros-estado .filtro-chip').forEach((b) => {
  b.classList.toggle('is-active', b.dataset.estado === filtroEstado);
});
document.querySelectorAll('#filtros-tipo .filtro-chip').forEach((b) => {
  b.classList.toggle('is-active', b.dataset.tipo === filtroTipo);
});
document.getElementById('orden-asignaturas').value = ordenActual;
document.getElementById('buscador-asignaturas').value = terminoBusqueda;

function progresoDe(asignatura) {
  if (asignatura.estado === 'superada' || asignatura.estado === 'no_superada') return 100;
  if (asignatura.estado === 'cursando') return asignatura.porcentaje_evaluado ?? 0;
  return 0;
}

function poblarFiltroCurso(anios) {
  const select = document.getElementById('filtro-curso');
  const numeros = anios.map((a) => a.numero).sort((a, b) => a - b);
  select.innerHTML = '<option value="todos">Todos los cursos</option>' +
    numeros.map((n) => `<option value="${n}">Año ${n}</option>`).join('');
  select.value = filtroCurso;
}

function aplicarFiltrosYOrden() {
  let lista = TODAS_ASIGNATURAS;

  if (filtroEstado !== 'todas') {
    lista = lista.filter((a) => a.estado === filtroEstado);
  }
  if (filtroTipo !== 'todos') {
    lista = lista.filter((a) => a.tipo === filtroTipo);
  }
  if (filtroCurso !== 'todos') {
    lista = lista.filter((a) => String(a.anio_numero) === filtroCurso);
  }
  if (terminoBusqueda.trim()) {
    const termino = terminoBusqueda.trim().toLowerCase();
    lista = lista.filter((a) => a.nombre.toLowerCase().includes(termino));
  }

  const conEntrega = (a) => PROXIMA_ENTREGA_POR_ASIGNATURA[a.id]?.fecha || '9999-99-99';

  lista = [...lista].sort((a, b) => {
    switch (ordenActual) {
      case 'creditos':
        return b.creditos_ects - a.creditos_ects;
      case 'curso':
        return a.anio_numero - b.anio_numero || a.cuatrimestre_numero - b.cuatrimestre_numero;
      case 'entrega':
        return conEntrega(a).localeCompare(conEntrega(b));
      default:
        return a.nombre.localeCompare(b.nombre);
    }
  });

  return lista;
}

function renderizar() {
  const grid = document.getElementById('asignaturas-grid');
  const lista = aplicarFiltrosYOrden();

  if (lista.length === 0) {
    grid.innerHTML = `
      <div class="ds-empty-state" style="grid-column: 1 / -1">
        <div class="ds-empty-state-icon">🔍</div>
        <div class="ds-empty-state-title">Sin resultados</div>
        <p class="ds-empty-state-description">Prueba a cambiar la búsqueda o los filtros.</p>
      </div>
    `;
    if (cargaInicial) { reanimar(grid); cargaInicial = false; }
    return;
  }

  grid.innerHTML = lista.map((a) => {
    const entrega = PROXIMA_ENTREGA_POR_ASIGNATURA[a.id];
    const entregaTexto = entrega
      ? `Próxima entrega: ${escapeHtml(entrega.titulo)} · ${calcularCountdown(entrega.fecha)}`
      : 'Sin próxima entrega';

    const evaluacion = PROXIMA_EVALUACION_POR_ASIGNATURA[a.id];
    const evaluacionTexto = evaluacion
      ? `Próxima evaluación: ${escapeHtml(evaluacion.titulo)} · ${calcularCountdown(evaluacion.fecha)}`
      : null;

    const notaTexto = a.nota_actual != null
      ? `Nota: ${formatoNota(a.nota_actual)}`
      : (a.evaluaciones_pendientes > 0 ? `Evaluaciones restantes: ${a.evaluaciones_pendientes}` : null);

    return `
      <a class="ds-card ds-card--interactive asignatura-card" href="/vista/asignaturas/${a.id}" data-id="${a.id}">
        <div class="asignatura-card-header">
          <p class="ds-h3">${a.siglas ? `${escapeHtml(a.siglas)} · ` : ''}${escapeHtml(a.nombre)}</p>
          <div class="asignatura-card-badges">
            <span class="ds-badge ${BADGE_POR_ESTADO[a.estado]}">${ETIQUETA_ESTADO[a.estado]}</span>
            <span class="ds-badge ds-badge-outline">${a.tipo === 'optativa' ? 'Optativa' : 'Obligatoria'}</span>
          </div>
        </div>
        <p class="ds-caption asignatura-card-meta">${a.creditos_ects} ECTS · Año ${a.anio_numero} · Cuatrimestre ${a.cuatrimestre_numero}</p>
        <div class="asignatura-card-estado-notas">
          <span class="ds-badge ${BADGE_POR_ESTADO_NOTAS[a.estado_notas]}">${ETIQUETA_ESTADO_NOTAS[a.estado_notas]}</span>
          ${notaTexto ? `<span class="ds-caption">${notaTexto}</span>` : ''}
        </div>
        <div class="asignatura-card-progreso">
          <div class="ds-progress"><div class="ds-progress-bar" style="width:${progresoDe(a)}%"></div></div>
        </div>
        <p class="ds-caption asignatura-card-entrega">${evaluacionTexto || entregaTexto}</p>
      </a>
    `;
  }).join('');

  if (cargaInicial) {
    reanimar(grid);
    cargaInicial = false;
  }

  grid.querySelectorAll('.asignatura-card').forEach((tarjeta) => {
    tarjeta.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const id = parseInt(tarjeta.dataset.id, 10);
      const asignatura = TODAS_ASIGNATURAS.find((a) => a.id === id);
      if (!asignatura) return;
      abrirMenuContextual([
        { etiqueta: 'Abrir', accion: () => { window.location.href = tarjeta.getAttribute('href'); } },
        { etiqueta: 'Marcar como cursando', accion: () => cambiarEstadoAsignatura(id, 'cursando') },
        { etiqueta: 'Marcar como superada', accion: () => cambiarEstadoAsignatura(id, 'superada') },
        { separador: true },
        { etiqueta: 'Eliminar', peligroso: true, accion: () => eliminarAsignatura(id, asignatura.nombre) },
      ], { x: e.clientX, y: e.clientY, anclaEl: tarjeta });
    });
  });
}

async function cambiarEstadoAsignatura(id, estado) {
  try {
    const meta = document.querySelector('meta[name="csrf-token"]');
    const res = await fetch(`/api/asignaturas/${id}/estado`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': meta ? meta.content : '' },
      body: JSON.stringify({ estado }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || `Error ${res.status}`);
    }
    mostrarToast('Estado actualizado', 'success');
    await cargarDatos();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
}

async function eliminarAsignatura(id, nombre) {
  if (!confirm(`¿Eliminar la asignatura "${nombre}"? Esta acción no se puede deshacer.`)) return;
  try {
    const meta = document.querySelector('meta[name="csrf-token"]');
    const res = await fetch(`/asignaturas/${id}`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': meta ? meta.content : '' },
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || `Error ${res.status}`);
    }
    mostrarToast('Asignatura eliminada', 'success');
    await cargarDatos();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
}

document.getElementById('buscador-asignaturas').addEventListener('input', (e) => {
  terminoBusqueda = e.target.value;
  layoutState.set('asignaturas-busqueda', terminoBusqueda);
  renderizar();
});

document.getElementById('filtros-estado').addEventListener('click', (e) => {
  const boton = e.target.closest('.filtro-chip');
  if (!boton) return;
  document.querySelectorAll('.filtro-chip').forEach((b) => b.classList.remove('is-active'));
  boton.classList.add('is-active');
  filtroEstado = boton.dataset.estado;
  layoutState.set('asignaturas-filtro-estado', filtroEstado);
  renderizar();
});

document.getElementById('filtros-tipo').addEventListener('click', (e) => {
  const boton = e.target.closest('.filtro-chip');
  if (!boton) return;
  document.querySelectorAll('#filtros-tipo .filtro-chip').forEach((b) => b.classList.remove('is-active'));
  boton.classList.add('is-active');
  filtroTipo = boton.dataset.tipo;
  layoutState.set('asignaturas-filtro-tipo', filtroTipo);
  renderizar();
});

document.getElementById('filtro-curso').addEventListener('change', (e) => {
  filtroCurso = e.target.value;
  layoutState.set('asignaturas-filtro-curso', filtroCurso);
  renderizar();
});

document.getElementById('orden-asignaturas').addEventListener('change', (e) => {
  ordenActual = e.target.value;
  layoutState.set('asignaturas-orden', ordenActual);
  renderizar();
});

// --- Panel "Optativas por elegir" (catálogo + creación a mano + quitar elección) ---

async function apiPost(path, body) {
  const meta = document.querySelector('meta[name="csrf-token"]');
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': meta ? meta.content : '' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Error ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

function renderOptativasPanel() {
  const panel = document.getElementById('optativas-panel');
  const contador = document.getElementById('optativas-panel-contador');
  const cuerpo = document.getElementById('optativas-panel-body');

  if (OPTATIVAS_POR_ELEGIR.length === 0) {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = '';
  contador.textContent = OPTATIVAS_POR_ELEGIR.length;

  const porCuatrimestre = new Map();
  for (const o of OPTATIVAS_POR_ELEGIR) {
    const clave = o.cuatrimestre_id;
    if (!porCuatrimestre.has(clave)) porCuatrimestre.set(clave, { anio: o.anio_numero, cuatrimestre: o.cuatrimestre_numero, items: [] });
    porCuatrimestre.get(clave).items.push(o);
  }
  const grupos = [...porCuatrimestre.entries()].sort((a, b) => a[1].cuatrimestre - b[1].cuatrimestre);

  cuerpo.innerHTML = grupos.map(([cuatrimestreId, grupo]) => `
    <div class="optativas-grupo" data-cuatrimestre-id="${cuatrimestreId}">
      <h3 class="ds-h3 optativas-grupo-titulo">Año ${grupo.anio} · Cuatrimestre ${grupo.cuatrimestre}</h3>
      <div class="optativas-catalogo-lista">
        ${grupo.items.map((o) => `
          <div class="optativa-catalogo-item" data-id="${o.id}">
            <div class="optativa-catalogo-item-nombre">
              <span class="ds-body">${escapeHtml(o.nombre)}</span>
              <span class="ds-caption">${o.creditos_ects} ECTS</span>
            </div>
            <div class="optativa-catalogo-item-acciones">
              <button type="button" class="ds-btn ds-btn-secondary btn-elegir-optativa" data-estado="cursando">Cursando</button>
              <button type="button" class="ds-btn ds-btn-secondary btn-elegir-optativa" data-estado="pendiente">Pendiente</button>
            </div>
          </div>
        `).join('')}
      </div>
      <form class="optativas-crear-form form-crear-optativa">
        <div class="ds-field" style="flex-basis:220px">
          <label class="ds-label">Crear optativa a mano</label>
          <input type="text" class="ds-input campo-nombre-optativa" placeholder="Nombre de la optativa" required>
        </div>
        <div class="ds-field" style="flex-basis:100px">
          <label class="ds-label">ECTS</label>
          <input type="number" class="ds-input campo-ects-optativa" min="0" step="0.5" required>
        </div>
        <div class="ds-field" style="flex-basis:140px">
          <label class="ds-label">Estado inicial</label>
          <select class="ds-select campo-estado-optativa">
            <option value="cursando">Cursando</option>
            <option value="pendiente">Pendiente</option>
          </select>
        </div>
        <button type="submit" class="ds-btn ds-btn-secondary">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-plus"></use></svg>
          Añadir
        </button>
      </form>
    </div>
  `).join('');

  cuerpo.querySelectorAll('.btn-elegir-optativa').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const item = btn.closest('.optativa-catalogo-item');
      const asignaturaId = item.dataset.id;
      btn.classList.add('is-loading');
      try {
        const cuatrimestreId = btn.closest('.optativas-grupo').dataset.cuatrimestreId;
        await apiPost(`/cuatrimestres/${cuatrimestreId}/optativas/elegir`, {
          asignatura_id: parseInt(asignaturaId, 10),
          estado: btn.dataset.estado,
        });
        mostrarToast('Optativa elegida', 'success');
        await cargarDatos();
      } catch (err) {
        mostrarToast(err.message, 'danger');
      } finally {
        btn.classList.remove('is-loading');
      }
    });
  });

  cuerpo.querySelectorAll('.form-crear-optativa').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const cuatrimestreId = form.closest('.optativas-grupo').dataset.cuatrimestreId;
      const nombre = form.querySelector('.campo-nombre-optativa').value.trim();
      const ects = parseFloat(form.querySelector('.campo-ects-optativa').value);
      const estado = form.querySelector('.campo-estado-optativa').value;
      if (!nombre || Number.isNaN(ects)) return;
      const boton = form.querySelector('button[type="submit"]');
      boton.classList.add('is-loading');
      try {
        await apiPost(`/cuatrimestres/${cuatrimestreId}/optativas/elegir`, {
          nombre, creditos_ects: ects, estado,
        });
        mostrarToast('Optativa creada', 'success');
        await cargarDatos();
      } catch (err) {
        mostrarToast(err.message, 'danger');
      } finally {
        boton.classList.remove('is-loading');
      }
    });
  });
}

document.getElementById('btn-toggle-optativas').addEventListener('click', () => {
  const panel = document.getElementById('optativas-panel');
  const cuerpo = document.getElementById('optativas-panel-body');
  const abierto = panel.classList.toggle('is-open');
  cuerpo.style.display = abierto ? '' : 'none';
});

async function cargarDatos() {
  const anios = await api('/anios');
  const detalles = await Promise.all(anios.map((a) => api(`/anios/${a.id}`)));

  TODAS_ASIGNATURAS = [];
  OPTATIVAS_POR_ELEGIR = [];
  for (const anio of detalles) {
    for (const cuatrimestre of anio.cuatrimestres) {
      for (const asignatura of cuatrimestre.asignaturas) {
        const conCurso = {
          ...asignatura,
          anio_numero: anio.numero,
          cuatrimestre_numero: cuatrimestre.numero,
          cuatrimestre_id: cuatrimestre.id,
        };
        if (asignatura.estado === 'no_elegida') {
          OPTATIVAS_POR_ELEGIR.push(conCurso);
          continue;
        }
        TODAS_ASIGNATURAS.push(conCurso);
      }
    }
  }
  renderOptativasPanel();

  const tareas = await api('/tareas?completada=false');
  PROXIMA_ENTREGA_POR_ASIGNATURA = {};
  PROXIMA_EVALUACION_POR_ASIGNATURA = {};
  for (const tarea of tareas) {
    if (!tarea.asignatura_id) continue;
    const actual = PROXIMA_ENTREGA_POR_ASIGNATURA[tarea.asignatura_id];
    if (!actual || tarea.fecha < actual.fecha) {
      PROXIMA_ENTREGA_POR_ASIGNATURA[tarea.asignatura_id] = tarea;
    }
    if (TIPOS_TAREA_EXAMEN.includes(tarea.tipo)) {
      const actualEval = PROXIMA_EVALUACION_POR_ASIGNATURA[tarea.asignatura_id];
      if (!actualEval || tarea.fecha < actualEval.fecha) {
        PROXIMA_EVALUACION_POR_ASIGNATURA[tarea.asignatura_id] = tarea;
      }
    }
  }

  poblarFiltroCurso(detalles);
  renderizar();
}

cargarDatos();
