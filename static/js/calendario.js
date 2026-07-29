const _params = new URLSearchParams(window.location.search);
const _anioParam = parseInt(_params.get('anio'), 10);
const _mesParam = parseInt(_params.get('mes'), 10);
let fechaActual = (_anioParam && _mesParam) ? new Date(_anioParam, _mesParam - 1, 1) : new Date();

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

const NOMBRES_MES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];
const NOMBRES_DIA_CORTO = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const ETIQUETA_TIPO = {
  examen_parcial: 'Examen parcial', examen_final: 'Examen final', recuperacion: 'Recuperación',
  entrega: 'Entrega', tutoria: 'Tutoría', evento: 'Evento', tarea_general: 'Tarea general',
  examen: 'Examen', // tipo histórico, se mantiene por compatibilidad con tareas ya creadas
};

// --- Estado ---
let vistaActual = 'mensual';
let filtroAsignatura = '';
let filtroTipo = '';
let TODAS_TAREAS = [];
let ASIGNATURAS = [];

function nombreConSiglas(a) {
  return a.siglas ? `${a.siglas} · ${a.nombre}` : a.nombre;
}

function fechaISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function inicioDeSemana(fecha) {
  const d = new Date(fecha);
  const diaSemana = (d.getDay() + 6) % 7; // lunes = 0
  d.setDate(d.getDate() - diaSemana);
  d.setHours(0, 0, 0, 0);
  return d;
}

// --- Carga de asignaturas para selects (filtro + formulario) ---

async function cargarAsignaturasSelects() {
  ASIGNATURAS = await api('/asignaturas');
  ASIGNATURAS.sort((a, b) => nombreConSiglas(a).localeCompare(nombreConSiglas(b)));

  const opciones = ASIGNATURAS
    .filter((a) => a.estado !== 'no_elegida')
    .map((a) => `<option value="${a.id}">${escapeHtml(nombreConSiglas(a))}</option>`)
    .join('');

  document.getElementById('filtro-asignatura').innerHTML = '<option value="">Todas</option>' + opciones;
  document.getElementById('tarea-asignatura').innerHTML = '<option value="">(ninguna)</option>' + opciones;
}

// --- Documento vinculado (spec V2.2_VISOR_PDF, "integración con asignaturas y exámenes") ---

async function poblarSelectDocumentos(asignaturaId, documentoIdSeleccionado) {
  const select = document.getElementById('tarea-documento');
  if (!asignaturaId) {
    select.innerHTML = '<option value="">(ninguno)</option>';
    select.disabled = true;
    return;
  }
  select.disabled = false;
  try {
    const documentos = await api(`/asignaturas/${asignaturaId}/documentos?solo_pdf=1`);
    const opciones = documentos
      .map((d) => `<option value="${d.id}">${escapeHtml(d.nombre_archivo)}</option>`)
      .join('');
    select.innerHTML = '<option value="">(ninguno)</option>' + opciones;
    select.value = documentoIdSeleccionado || '';
  } catch (err) {
    select.innerHTML = '<option value="">(ninguno)</option>';
  }
}

document.getElementById('tarea-asignatura').addEventListener('change', (e) => {
  poblarSelectDocumentos(e.target.value || null, null);
});

// --- Carga de datos (todas las tareas que cumplen los filtros activos) ---

async function cargarDatos() {
  const params = new URLSearchParams();
  if (filtroAsignatura) params.set('asignatura_id', filtroAsignatura);
  if (filtroTipo) params.set('tipo', filtroTipo);
  TODAS_TAREAS = await api(`/tareas?${params}`);
  renderVistaActual();
}

function renderVistaActual() {
  document.getElementById('vista-mensual').style.display = vistaActual === 'mensual' ? '' : 'none';
  document.getElementById('vista-semanal').style.display = vistaActual === 'semanal' ? '' : 'none';
  document.getElementById('vista-agenda').style.display = vistaActual === 'agenda' ? '' : 'none';

  const navVisible = vistaActual !== 'agenda';
  document.getElementById('btn-periodo-anterior').style.visibility = navVisible ? 'visible' : 'hidden';
  document.getElementById('btn-periodo-siguiente').style.visibility = navVisible ? 'visible' : 'hidden';

  if (vistaActual === 'mensual') renderMensual();
  else if (vistaActual === 'semanal') renderSemanal();
  else renderAgenda();
}

// --- Elemento visual de una tarea (reutilizado en las 3 vistas con distinto detalle) ---

function chipTarea(tarea, { detallado = false } = {}) {
  const item = document.createElement('div');
  item.className = `tarea-item prioridad-${tarea.prioridad}${tarea.completada ? ' completada' : ''}`;
  item.title = `${ETIQUETA_TIPO[tarea.tipo] || tarea.tipo}${tarea.asignatura_nombre ? ' · ' + tarea.asignatura_nombre : ''} (clic para ver/editar)`;
  item.draggable = true;
  item.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('application/x-tarea-id', String(tarea.id));
    e.dataTransfer.effectAllowed = 'move';
  });
  item.addEventListener('contextmenu', async (e) => {
    e.preventDefault();
    const opciones = [
      { etiqueta: 'Editar', accion: () => abrirDialogoEdicion(tarea) },
      { etiqueta: 'Duplicar', accion: () => duplicarTarea(tarea) },
    ];
    try {
      const espacio = await api(`/tareas/${tarea.id}/espacio-estudio`);
      opciones.push({ etiqueta: '📚 Abrir Espacio de Estudio', accion: () => { window.location.href = `/vista/espacios-estudio/${espacio.id}`; } });
    } catch (err) {
      // 404: sin Espacio de Estudio vinculado, no se añade la opción.
    }
    opciones.push({ separador: true });
    opciones.push({ etiqueta: 'Eliminar', peligroso: true, accion: () => confirmarBorrarTarea(tarea) });
    abrirMenuContextual(opciones, { x: e.clientX, y: e.clientY, anclaEl: item });
  });

  const cuerpo = document.createElement('div');
  cuerpo.className = 'tarea-item-cuerpo';
  if (detallado) {
    // Formato "los exámenes deben mostrar directamente hora y aula sin abrir el evento"
    const siglas = tarea.asignatura_siglas ? `<span class="tarea-item-siglas">${escapeHtml(tarea.asignatura_siglas)}</span>` : '';
    const horas = tarea.hora_inicio ? `<span class="tarea-item-horas">${tarea.hora_inicio}${tarea.hora_fin ? '–' + tarea.hora_fin : ''}</span>` : '';
    const aula = tarea.aula ? `<span class="tarea-item-aula">${escapeHtml(tarea.aula)}</span>` : '';
    cuerpo.innerHTML = `
      ${siglas}
      <span class="tarea-item-tipo">${escapeHtml(ETIQUETA_TIPO[tarea.tipo] || tarea.tipo)}</span>
      <span class="tarea-item-titulo">${escapeHtml(tarea.titulo)}</span>
      ${horas}${aula}
    `;
  } else {
    const prefijo = [tarea.hora_inicio, tarea.asignatura_siglas].filter(Boolean).join(' ');
    cuerpo.textContent = prefijo ? `${prefijo} · ${tarea.titulo}` : tarea.titulo;
  }
  cuerpo.addEventListener('click', () => abrirDialogoEdicion(tarea));
  item.appendChild(cuerpo);

  const btnBorrar = document.createElement('button');
  btnBorrar.className = 'btn-borrar-tarea';
  btnBorrar.type = 'button';
  btnBorrar.innerHTML = '<svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>';
  btnBorrar.title = 'Eliminar tarea/evento';
  btnBorrar.setAttribute('aria-label', 'Eliminar tarea/evento');
  btnBorrar.addEventListener('click', (e) => {
    e.stopPropagation();
    confirmarBorrarTarea(tarea);
  });
  item.appendChild(btnBorrar);

  return item;
}

// --- Vista mensual ---

function renderMensual() {
  const anio = fechaActual.getFullYear();
  const mes = fechaActual.getMonth() + 1;
  document.getElementById('periodo-actual-label').textContent = `${NOMBRES_MES[mes - 1]} ${anio}`;

  const porDia = {};
  for (const t of TODAS_TAREAS) {
    (porDia[t.fecha] = porDia[t.fecha] || []).push(t);
  }

  const grid = document.getElementById('calendario-grid');
  grid.innerHTML = '';

  const primerDiaSemana = (new Date(anio, mes - 1, 1).getDay() + 6) % 7;
  const diasEnMes = new Date(anio, mes, 0).getDate();

  for (let i = 0; i < primerDiaSemana; i++) {
    const vacio = document.createElement('div');
    vacio.className = 'dia-vacio';
    grid.appendChild(vacio);
  }

  for (let dia = 1; dia <= diasEnMes; dia++) {
    const fecha = `${anio}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
    const celda = document.createElement('div');
    celda.className = 'dia-celda';
    celda.innerHTML = `<div class="dia-numero">${dia}</div>`;

    for (const tarea of (porDia[fecha] || [])) {
      celda.appendChild(chipTarea(tarea));
    }

    celda.addEventListener('dragover', (e) => {
      e.preventDefault();
      celda.classList.add('dragover');
    });
    celda.addEventListener('dragleave', () => celda.classList.remove('dragover'));
    celda.addEventListener('drop', (e) => {
      e.preventDefault();
      celda.classList.remove('dragover');
      const tareaId = e.dataTransfer.getData('application/x-tarea-id');
      if (tareaId) moverTareaAFecha(tareaId, fecha);
    });

    grid.appendChild(celda);
  }
  reanimar(grid);
}

// --- Vista semanal ---

function renderSemanal() {
  const inicio = inicioDeSemana(fechaActual);
  const dias = [...Array(7)].map((_, i) => {
    const d = new Date(inicio);
    d.setDate(d.getDate() + i);
    return d;
  });

  const finSemana = dias[6];
  const mismomes = inicio.getMonth() === finSemana.getMonth();
  document.getElementById('periodo-actual-label').textContent = mismomes
    ? `${inicio.getDate()}–${finSemana.getDate()} ${NOMBRES_MES[inicio.getMonth()]} ${inicio.getFullYear()}`
    : `${inicio.getDate()} ${NOMBRES_MES[inicio.getMonth()]} – ${finSemana.getDate()} ${NOMBRES_MES[finSemana.getMonth()]} ${finSemana.getFullYear()}`;

  const cabecera = document.getElementById('calendario-semana-cabecera');
  cabecera.innerHTML = dias.map((d, i) => `<span>${NOMBRES_DIA_CORTO[i]} ${d.getDate()}</span>`).join('');

  const porDia = {};
  for (const t of TODAS_TAREAS) {
    (porDia[t.fecha] = porDia[t.fecha] || []).push(t);
  }

  const grid = document.getElementById('calendario-semana-grid');
  grid.innerHTML = '';
  dias.forEach((d, i) => {
    const columna = document.createElement('div');
    columna.className = 'dia-celda dia-celda--semana';
    const tareasDelDia = (porDia[fechaISO(d)] || []).sort((a, b) => (a.hora_inicio || '99:99').localeCompare(b.hora_inicio || '99:99'));
    // Visible solo en móvil (la cabecera compartida ya lo dice en escritorio, ver CSS):
    // sin esto, al apilar la semana como agenda diaria se perdería de qué día es cada bloque.
    const etiqueta = document.createElement('p');
    etiqueta.className = 'dia-celda-semana-etiqueta';
    etiqueta.textContent = `${NOMBRES_DIA_CORTO[i]} ${d.getDate()}`;
    columna.appendChild(etiqueta);
    for (const tarea of tareasDelDia) {
      columna.appendChild(chipTarea(tarea, { detallado: true }));
    }
    grid.appendChild(columna);
  });
  reanimar(grid);
}

// --- Vista agenda ---

function renderAgenda() {
  document.getElementById('periodo-actual-label').textContent = 'Todas las próximas';

  const ordenadas = [...TODAS_TAREAS].sort((a, b) =>
    a.fecha.localeCompare(b.fecha) || (a.hora_inicio || '99:99').localeCompare(b.hora_inicio || '99:99')
  );

  const contenedor = document.getElementById('calendario-agenda-lista');
  if (ordenadas.length === 0) {
    contenedor.innerHTML = `
      <div class="ds-empty-state">
        <div class="ds-empty-state-icon">🗓️</div>
        <div class="ds-empty-state-title">Sin eventos</div>
        <p class="ds-empty-state-description">Prueba a cambiar los filtros o añade una nueva tarea/evento.</p>
      </div>
    `;
    return;
  }

  contenedor.innerHTML = '';
  let diaAnterior = null;
  for (const tarea of ordenadas) {
    if (tarea.fecha !== diaAnterior) {
      diaAnterior = tarea.fecha;
      const fechaObj = new Date(`${tarea.fecha}T00:00:00`);
      const cabecera = document.createElement('h3');
      cabecera.className = 'ds-h3 calendario-agenda-dia';
      cabecera.textContent = fechaObj.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
      contenedor.appendChild(cabecera);
    }
    contenedor.appendChild(chipTarea(tarea, { detallado: true }));
  }
  reanimar(contenedor);
}

async function alternarCompletada(tarea) {
  await api(`/tareas/${tarea.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ completada: !tarea.completada }),
  });
  await cargarDatos();
}

async function confirmarBorrarTarea(tarea) {
  if (!confirm(`¿Borrar "${tarea.titulo}"? Esta acción no se puede deshacer.`)) return;
  await api(`/tareas/${tarea.id}`, { method: 'DELETE' });
  await cargarDatos();
  mostrarToast(`"${tarea.titulo}" eliminada`, 'success');
}

async function duplicarTarea(tarea) {
  const copia = {
    titulo: tarea.titulo,
    fecha: tarea.fecha,
    tipo: tarea.tipo,
    prioridad: tarea.prioridad,
    asignatura_id: tarea.asignatura_id || null,
    documento_id: tarea.documento_id || null,
    hora_inicio: tarea.hora_inicio || null,
    hora_fin: tarea.hora_fin || null,
    aula: tarea.aula || null,
    ubicacion: tarea.ubicacion || null,
    descripcion: tarea.descripcion || null,
    recordatorio: tarea.recordatorio ?? null,
    link_relacionado: tarea.link_relacionado || null,
  };
  try {
    await api('/tareas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(copia),
    });
    await cargarDatos();
    mostrarToast(`"${tarea.titulo}" duplicada`, 'success');
  } catch (err) {
    mostrarToast('Error al duplicar: ' + err.message, 'danger');
  }
}

async function moverTareaAFecha(tareaId, fecha) {
  try {
    await api(`/tareas/${tareaId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fecha }),
    });
    await cargarDatos();
    mostrarToast('Fecha actualizada', 'success');
  } catch (err) {
    mostrarToast('Error al mover: ' + err.message, 'danger');
  }
}

// --- Navegación de periodo + cambio de vista ---

document.getElementById('btn-periodo-anterior').addEventListener('click', () => {
  if (vistaActual === 'semanal') fechaActual.setDate(fechaActual.getDate() - 7);
  else fechaActual.setMonth(fechaActual.getMonth() - 1);
  renderVistaActual();
});
document.getElementById('btn-periodo-siguiente').addEventListener('click', () => {
  if (vistaActual === 'semanal') fechaActual.setDate(fechaActual.getDate() + 7);
  else fechaActual.setMonth(fechaActual.getMonth() + 1);
  renderVistaActual();
});

document.getElementById('vista-chips').addEventListener('click', (e) => {
  const boton = e.target.closest('.filtro-chip');
  if (!boton) return;
  document.querySelectorAll('#vista-chips .filtro-chip').forEach((b) => b.classList.remove('is-active'));
  boton.classList.add('is-active');
  vistaActual = boton.dataset.vista;
  renderVistaActual();
});

document.getElementById('filtro-asignatura').addEventListener('change', (e) => {
  filtroAsignatura = e.target.value;
  cargarDatos();
});
document.getElementById('filtro-tipo').addEventListener('change', (e) => {
  filtroTipo = e.target.value;
  cargarDatos();
});

// --- Diálogo crear/editar tarea ---

// Tipos para los que tiene sentido preparar un Espacio de Estudio (spec "Espacios
// de Estudio Inteligentes"): exámenes, entregas y eventos (exposiciones); se
// excluyen tarea_general/tutoria por no ser "objetivos" concretos que preparar.
const TIPOS_CON_ESPACIO_ESTUDIO = ['examen_parcial', 'examen_final', 'recuperacion', 'entrega', 'evento'];

function actualizarVisibilidadCampoEspacio() {
  const tipo = document.getElementById('tarea-tipo').value;
  const aplica = TIPOS_CON_ESPACIO_ESTUDIO.includes(tipo);
  const verEspacio = document.getElementById('tarea-espacio-ver');
  const yaTieneEspacio = verEspacio.style.display !== 'none';
  document.getElementById('campo-crear-espacio').style.display = (aplica && !yaTieneEspacio) ? '' : 'none';
  if (!aplica) verEspacio.style.display = 'none';
}

document.getElementById('tarea-tipo').addEventListener('change', actualizarVisibilidadCampoEspacio);

function limpiarFormularioTarea() {
  document.getElementById('form-tarea').reset();
  document.getElementById('tarea-id').value = '';
  document.getElementById('tarea-conflictos-aviso').style.display = 'none';
  document.getElementById('tarea-form-error').textContent = '';
  poblarSelectDocumentos(null, null);
  document.getElementById('tarea-documento-ver').style.display = 'none';
  document.getElementById('tarea-crear-espacio').checked = false;
  document.getElementById('tarea-espacio-ver').style.display = 'none';
  actualizarVisibilidadCampoEspacio();
}

document.getElementById('btn-nueva-tarea').addEventListener('click', () => {
  limpiarFormularioTarea();
  document.getElementById('dialog-tarea-titulo').textContent = 'Nueva tarea/evento';
  document.getElementById('btn-borrar-tarea-dialogo').style.display = 'none';
  document.getElementById('btn-exportar-tarea-ics').style.display = 'none';
  document.getElementById('tarea-fecha').value = fechaISO(vistaActual === 'agenda' ? new Date() : fechaActual);
  document.getElementById('dialog-tarea').showModal();
});

async function abrirDialogoEdicion(tarea) {
  limpiarFormularioTarea();
  document.getElementById('dialog-tarea-titulo').textContent = 'Editar tarea/evento';
  document.getElementById('tarea-id').value = tarea.id;
  document.getElementById('tarea-titulo').value = tarea.titulo;
  document.getElementById('tarea-tipo').value = ['examen_parcial', 'examen_final', 'recuperacion', 'entrega', 'tutoria', 'evento', 'tarea_general'].includes(tarea.tipo) ? tarea.tipo : 'tarea_general';
  document.getElementById('tarea-asignatura').value = tarea.asignatura_id || '';
  await poblarSelectDocumentos(tarea.asignatura_id || null, tarea.documento_id || null);
  const verPdf = document.getElementById('tarea-documento-ver');
  if (tarea.documento_id && tarea.asignatura_id) {
    verPdf.href = `/vista/asignaturas/${tarea.asignatura_id}?doc=${tarea.documento_id}`;
    verPdf.style.display = '';
  } else {
    verPdf.style.display = 'none';
  }
  document.getElementById('tarea-fecha').value = tarea.fecha;
  document.getElementById('tarea-hora-inicio').value = tarea.hora_inicio || '';
  document.getElementById('tarea-hora-fin').value = tarea.hora_fin || '';
  document.getElementById('tarea-aula').value = tarea.aula || '';
  document.getElementById('tarea-ubicacion').value = tarea.ubicacion || '';
  document.getElementById('tarea-descripcion').value = tarea.descripcion || '';
  document.getElementById('tarea-prioridad').value = tarea.prioridad;
  document.getElementById('tarea-recordatorio').value = tarea.recordatorio ?? '';
  document.getElementById('tarea-link').value = tarea.link_relacionado || '';

  document.getElementById('btn-borrar-tarea-dialogo').style.display = '';
  const btnExportar = document.getElementById('btn-exportar-tarea-ics');
  btnExportar.style.display = '';
  btnExportar.href = `/tareas/${tarea.id}/ics`;

  actualizarVisibilidadCampoEspacio();
  try {
    const espacio = await api(`/tareas/${tarea.id}/espacio-estudio`);
    const verEspacio = document.getElementById('tarea-espacio-ver');
    verEspacio.href = `/vista/espacios-estudio/${espacio.id}`;
    verEspacio.style.display = '';
    document.getElementById('campo-crear-espacio').style.display = 'none';
  } catch (err) {
    // 404: esta tarea todavía no tiene Espacio de Estudio, se deja el checkbox visible.
  }

  document.getElementById('dialog-tarea').showModal();
}

function cerrarDialogoTarea() {
  document.getElementById('dialog-tarea').close();
  limpiarFormularioTarea();
}

document.getElementById('btn-cancelar-tarea').addEventListener('click', cerrarDialogoTarea);

document.getElementById('btn-borrar-tarea-dialogo').addEventListener('click', async () => {
  const id = document.getElementById('tarea-id').value;
  const titulo = document.getElementById('tarea-titulo').value;
  if (!id) return;
  if (!confirm(`¿Borrar "${titulo}"? Esta acción no se puede deshacer.`)) return;
  await api(`/tareas/${id}`, { method: 'DELETE' });
  cerrarDialogoTarea();
  await cargarDatos();
  mostrarToast(`"${titulo}" eliminada`, 'success');
});

// Aviso de conflictos NO bloqueante: se comprueba en cuanto hay fecha+horas, pero
// nunca impide guardar (spec punto 7: "permite guardar igualmente").
async function comprobarConflictosFormulario() {
  const aviso = document.getElementById('tarea-conflictos-aviso');
  const fecha = document.getElementById('tarea-fecha').value;
  const horaInicio = document.getElementById('tarea-hora-inicio').value;
  const horaFin = document.getElementById('tarea-hora-fin').value;
  if (!fecha || !horaInicio || !horaFin) {
    aviso.style.display = 'none';
    return;
  }
  try {
    const { conflictos } = await api('/calendario/comprobar-conflictos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fecha, hora_inicio: horaInicio, hora_fin: horaFin,
        excluir_tarea_id: document.getElementById('tarea-id').value || null,
      }),
    });
    if (conflictos.length === 0) {
      aviso.style.display = 'none';
      return;
    }
    aviso.style.display = '';
    aviso.innerHTML = `
      <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-circle-alert"></use></svg>
      <div>
        <strong>Choca con ${conflictos.length} evento${conflictos.length !== 1 ? 's' : ''}:</strong>
        <ul>
          ${conflictos.map((c) => `<li>${escapeHtml(c.asignatura_siglas || c.titulo)} · ${c.hora_inicio}–${c.hora_fin}${c.aula ? ' · ' + escapeHtml(c.aula) : ''}</li>`).join('')}
        </ul>
      </div>
    `;
  } catch (err) {
    aviso.style.display = 'none';
  }
}

['tarea-fecha', 'tarea-hora-inicio', 'tarea-hora-fin'].forEach((id) => {
  document.getElementById(id).addEventListener('change', comprobarConflictosFormulario);
});

document.getElementById('form-tarea').addEventListener('submit', async (e) => {
  // preventDefault siempre lo primero: el formulario ya no depende de method="dialog"
  // nativo (algunos motores del WebView de escritorio no lo soportan bien y acababan
  // haciendo un submit real que recargaba toda la app), así que sin esto un submit
  // navegaría la página en vez de guardar por fetch.
  e.preventDefault();

  const id = document.getElementById('tarea-id').value;
  const asignaturaIdRaw = document.getElementById('tarea-asignatura').value;
  const documentoIdRaw = document.getElementById('tarea-documento').value;
  const recordatorioRaw = document.getElementById('tarea-recordatorio').value;
  const body = {
    titulo: document.getElementById('tarea-titulo').value,
    fecha: document.getElementById('tarea-fecha').value,
    tipo: document.getElementById('tarea-tipo').value,
    prioridad: document.getElementById('tarea-prioridad').value,
    asignatura_id: asignaturaIdRaw ? parseInt(asignaturaIdRaw, 10) : null,
    documento_id: documentoIdRaw ? parseInt(documentoIdRaw, 10) : null,
    hora_inicio: document.getElementById('tarea-hora-inicio').value || null,
    hora_fin: document.getElementById('tarea-hora-fin').value || null,
    aula: document.getElementById('tarea-aula').value.trim() || null,
    ubicacion: document.getElementById('tarea-ubicacion').value.trim() || null,
    descripcion: document.getElementById('tarea-descripcion').value.trim() || null,
    recordatorio: recordatorioRaw ? parseInt(recordatorioRaw, 10) : null,
    link_relacionado: document.getElementById('tarea-link').value.trim() || null,
  };

  const crearEspacio = document.getElementById('tarea-crear-espacio').checked
    && document.getElementById('campo-crear-espacio').style.display !== 'none';

  const btnGuardar = document.getElementById('btn-guardar-tarea');
  btnGuardar.classList.add('is-loading');
  try {
    let tareaGuardada;
    if (id) {
      tareaGuardada = await api(`/tareas/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } else {
      tareaGuardada = await api('/tareas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    }

    if (crearEspacio) {
      const espacio = await api('/espacios-estudio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tarea_evento_id: tareaGuardada.id }),
      });
      cerrarDialogoTarea();
      window.location.href = `/vista/espacios-estudio/${espacio.id}`;
      return;
    }

    cerrarDialogoTarea();
    await cargarDatos();
    mostrarToast(`"${body.titulo}" ${id ? 'actualizada' : 'añadida'}`, 'success');
  } catch (err) {
    const errorEl = document.getElementById('tarea-form-error');
    errorEl.innerHTML = '<svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-circle-alert"></use></svg><span></span>';
    errorEl.querySelector('span').textContent = err.message;
  } finally {
    btnGuardar.classList.remove('is-loading');
  }
});

cargarAsignaturasSelects().then(cargarDatos);
