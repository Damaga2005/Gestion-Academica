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

const NOMBRE_DIA = { 1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes' };
const ETIQUETA_TIPO_HORARIO = { teoria: 'Teoría', problemas: 'Problemas', laboratorio: 'Laboratorio', seminario: 'Seminario' };
const ETIQUETA_FRECUENCIA = { 1: 'Todas las semanas', 2: 'Cada dos semanas' };

// Cuadrícula de escritorio: franjas de media hora entre estas horas.
const GRID_HORA_INICIO = 8;
const GRID_HORA_FIN = 21;

function nombreConSiglas(a) {
  return a.siglas ? `${a.siglas} · ${a.nombre}` : a.nombre;
}

function minutosDesdeHHMM(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
}

let ASIGNATURAS = [];
let HORARIOS = [];

async function cargarAsignaturasSelect() {
  ASIGNATURAS = await api('/asignaturas');
  ASIGNATURAS.sort((a, b) => nombreConSiglas(a).localeCompare(nombreConSiglas(b)));
  const opciones = ASIGNATURAS
    .filter((a) => a.estado !== 'no_elegida')
    .map((a) => `<option value="${a.id}">${escapeHtml(nombreConSiglas(a))}</option>`)
    .join('');
  document.getElementById('horario-asignatura').innerHTML = '<option value="">Elige una asignatura…</option>' + opciones;
}

async function cargarHorarios() {
  HORARIOS = await api('/horarios');
  renderGridEscritorio();
  renderAgendaMovil();
}

// --- Cuadrícula de escritorio (lunes-viernes x franjas horarias) ---

function renderGridEscritorio() {
  const grid = document.getElementById('horario-grid');
  const totalFilas = (GRID_HORA_FIN - GRID_HORA_INICIO) * 2;

  grid.style.gridTemplateRows = `40px repeat(${totalFilas}, 28px)`;
  grid.innerHTML = '';

  // Esquina vacía + cabecera de días
  grid.appendChild(Object.assign(document.createElement('div'), { className: 'horario-grid-esquina' }));
  for (let dia = 1; dia <= 5; dia++) {
    const cab = document.createElement('div');
    cab.className = 'horario-grid-dia-cabecera';
    cab.textContent = NOMBRE_DIA[dia];
    cab.style.gridColumn = String(dia + 1);
    cab.style.gridRow = '1';
    grid.appendChild(cab);
  }

  // Etiquetas de hora (una por hora en punto)
  for (let h = GRID_HORA_INICIO; h < GRID_HORA_FIN; h++) {
    const etiqueta = document.createElement('div');
    etiqueta.className = 'horario-grid-hora';
    etiqueta.textContent = `${String(h).padStart(2, '0')}:00`;
    etiqueta.style.gridColumn = '1';
    etiqueta.style.gridRow = `${(h - GRID_HORA_INICIO) * 2 + 2} / span 2`;
    grid.appendChild(etiqueta);
  }

  // Líneas de fondo de cada franja (para que se vea la cuadrícula aunque no haya clase)
  for (let fila = 0; fila < totalFilas; fila++) {
    for (let dia = 1; dia <= 5; dia++) {
      const celda = document.createElement('div');
      celda.className = `horario-grid-celda${fila % 2 === 1 ? ' horario-grid-celda--media' : ''}`;
      celda.style.gridColumn = String(dia + 1);
      celda.style.gridRow = String(fila + 2);
      grid.appendChild(celda);
    }
  }

  // Bloques de clase/laboratorio
  for (const h of HORARIOS) {
    const inicioMin = minutosDesdeHHMM(h.hora_inicio);
    const finMin = minutosDesdeHHMM(h.hora_fin);
    const filaInicio = Math.round((inicioMin - GRID_HORA_INICIO * 60) / 30) + 2;
    const filaFin = Math.round((finMin - GRID_HORA_INICIO * 60) / 30) + 2;
    if (filaInicio < 2 || filaFin > totalFilas + 2) continue; // fuera del rango visible de la cuadrícula

    const bloque = document.createElement('button');
    bloque.type = 'button';
    bloque.className = `horario-bloque horario-bloque--${h.tipo}`;
    bloque.style.gridColumn = String(h.dia_semana + 1);
    bloque.style.gridRow = `${filaInicio} / ${filaFin}`;
    bloque.innerHTML = `
      <span class="horario-bloque-siglas">${escapeHtml(h.asignatura_siglas || h.asignatura_nombre)}</span>
      <span class="horario-bloque-tipo">${ETIQUETA_TIPO_HORARIO[h.tipo]}</span>
      <span class="horario-bloque-horas">${h.hora_inicio}–${h.hora_fin}</span>
      ${h.aula ? `<span class="horario-bloque-aula">${escapeHtml(h.aula)}</span>` : ''}
    `;
    bloque.addEventListener('click', () => abrirDialogoEdicion(h));
    grid.appendChild(bloque);
  }
}

// --- Agenda móvil (día a día, spec punto 3: no comprimir la cuadrícula) ---

function renderAgendaMovil() {
  const contenedor = document.getElementById('horario-agenda-movil');
  if (HORARIOS.length === 0) {
    contenedor.innerHTML = `
      <div class="ds-empty-state">
        <div class="ds-empty-state-icon">🗓️</div>
        <div class="ds-empty-state-title">Sin clases todavía</div>
        <p class="ds-empty-state-description">Añade tu primera clase o laboratorio recurrente.</p>
      </div>
    `;
    return;
  }

  const porDia = {};
  for (const h of HORARIOS) (porDia[h.dia_semana] = porDia[h.dia_semana] || []).push(h);
  for (const dia in porDia) porDia[dia].sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio));

  contenedor.innerHTML = [1, 2, 3, 4, 5].filter((d) => porDia[d]).map((dia) => `
    <h3 class="ds-h3 horario-agenda-dia">${NOMBRE_DIA[dia]}</h3>
    <div class="horario-agenda-lista" data-dia="${dia}"></div>
  `).join('');

  for (const dia of Object.keys(porDia)) {
    const lista = contenedor.querySelector(`.horario-agenda-lista[data-dia="${dia}"]`);
    if (!lista) continue;
    for (const h of porDia[dia]) {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = `horario-bloque horario-bloque--${h.tipo} horario-bloque--agenda`;
      item.innerHTML = `
        <span class="horario-bloque-siglas">${escapeHtml(h.asignatura_siglas || h.asignatura_nombre)}</span>
        <span class="horario-bloque-tipo">${ETIQUETA_TIPO_HORARIO[h.tipo]}</span>
        <span class="horario-bloque-horas">${h.hora_inicio}–${h.hora_fin}</span>
        ${h.aula ? `<span class="horario-bloque-aula">${escapeHtml(h.aula)}</span>` : ''}
      `;
      item.addEventListener('click', () => abrirDialogoEdicion(h));
      lista.appendChild(item);
    }
  }
}

// --- Diálogo crear/editar serie ---

function limpiarFormularioHorario() {
  document.getElementById('form-horario').reset();
  document.getElementById('horario-id').value = '';
  document.getElementById('horario-conflictos-aviso').style.display = 'none';
  document.getElementById('horario-form-error').textContent = '';
}

document.getElementById('btn-nuevo-horario').addEventListener('click', () => {
  limpiarFormularioHorario();
  document.getElementById('dialog-horario-titulo').textContent = 'Nueva clase/laboratorio';
  document.getElementById('btn-borrar-horario').style.display = 'none';
  document.getElementById('btn-exportar-horario-ics').style.display = 'none';
  document.getElementById('dialog-horario').showModal();
});

function abrirDialogoEdicion(horario) {
  limpiarFormularioHorario();
  document.getElementById('dialog-horario-titulo').textContent =
    `${horario.asignatura_nombre} · ${horario.asignatura_siglas || ''}`.replace(/ · $/, '');
  document.getElementById('horario-id').value = horario.id;
  document.getElementById('horario-asignatura').value = horario.asignatura_id;
  document.getElementById('horario-tipo').value = horario.tipo;
  document.getElementById('horario-dia').value = horario.dia_semana;
  document.getElementById('horario-hora-inicio').value = horario.hora_inicio;
  document.getElementById('horario-hora-fin').value = horario.hora_fin;
  document.getElementById('horario-aula').value = horario.aula || '';
  document.getElementById('horario-frecuencia').value = horario.intervalo_semanas;
  document.getElementById('horario-fecha-inicio').value = horario.fecha_inicio;
  document.getElementById('horario-fecha-fin').value = horario.fecha_fin;
  document.getElementById('horario-notas').value = horario.notas || '';

  document.getElementById('btn-borrar-horario').style.display = '';
  const btnExportar = document.getElementById('btn-exportar-horario-ics');
  btnExportar.style.display = '';
  btnExportar.href = `/horarios/${horario.id}/ics`;

  document.getElementById('dialog-horario').showModal();
}

function cerrarDialogoHorario() {
  document.getElementById('dialog-horario').close();
  limpiarFormularioHorario();
}

document.getElementById('btn-cancelar-horario').addEventListener('click', cerrarDialogoHorario);

document.getElementById('btn-borrar-horario').addEventListener('click', async () => {
  const id = document.getElementById('horario-id').value;
  if (!id) return;
  // Texto de confirmación literal (spec punto 6): no se implementan excepciones por
  // sesión suelta, así que hay que dejar clarísimo que se borra la serie entera.
  if (!confirm('Se eliminarán todas las sesiones de esta serie.\n\n¿Continuar?')) return;
  await api(`/horarios/${id}`, { method: 'DELETE' });
  cerrarDialogoHorario();
  await cargarHorarios();
  mostrarToast('Serie eliminada', 'success');
});

function mostrarAvisoConflictosHorario(conflictos) {
  const aviso = document.getElementById('horario-conflictos-aviso');
  if (!conflictos || conflictos.length === 0) {
    aviso.style.display = 'none';
    return;
  }
  aviso.style.display = '';
  aviso.innerHTML = `
    <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-circle-alert"></use></svg>
    <div>
      <strong>Esta serie choca con ${conflictos.length} ${conflictos.length !== 1 ? 'sesiones existentes' : 'sesión existente'}:</strong>
      <ul>
        ${conflictos.slice(0, 8).map((c) => `<li>${escapeHtml(c.asignatura_siglas || c.titulo)} · ${c.fecha} · ${c.hora_inicio}–${c.hora_fin}</li>`).join('')}
        ${conflictos.length > 8 ? `<li>… y ${conflictos.length - 8} más</li>` : ''}
      </ul>
      <p class="ds-caption">Se ha guardado igualmente; puedes ajustarlo si quieres evitar el choque.</p>
    </div>
  `;
}

document.getElementById('form-horario').addEventListener('submit', async (e) => {
  e.preventDefault();

  const id = document.getElementById('horario-id').value;
  const body = {
    asignatura_id: parseInt(document.getElementById('horario-asignatura').value, 10),
    tipo: document.getElementById('horario-tipo').value,
    dia_semana: parseInt(document.getElementById('horario-dia').value, 10),
    hora_inicio: document.getElementById('horario-hora-inicio').value,
    hora_fin: document.getElementById('horario-hora-fin').value,
    aula: document.getElementById('horario-aula').value.trim() || null,
    intervalo_semanas: parseInt(document.getElementById('horario-frecuencia').value, 10),
    fecha_inicio: document.getElementById('horario-fecha-inicio').value,
    fecha_fin: document.getElementById('horario-fecha-fin').value,
    notas: document.getElementById('horario-notas').value.trim() || null,
  };

  const btnGuardar = document.getElementById('btn-guardar-horario');
  btnGuardar.classList.add('is-loading');
  try {
    const resultado = id
      ? await api(`/horarios/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      : await api('/horarios', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

    await cargarHorarios();

    if (resultado.conflictos && resultado.conflictos.length > 0) {
      // No se cierra el diálogo: se deja ver la advertencia (no bloqueante, spec
      // punto 7) antes de que el usuario decida cerrarlo él mismo.
      document.getElementById('horario-id').value = resultado.id;
      mostrarAvisoConflictosHorario(resultado.conflictos);
      mostrarToast('Guardado con conflictos de horario', 'warning');
    } else {
      cerrarDialogoHorario();
      mostrarToast(id ? 'Horario actualizado' : 'Horario añadido', 'success');
    }
  } catch (err) {
    const errorEl = document.getElementById('horario-form-error');
    errorEl.innerHTML = '<svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-circle-alert"></use></svg><span></span>';
    errorEl.querySelector('span').textContent = err.message;
  } finally {
    btnGuardar.classList.remove('is-loading');
  }
});

cargarAsignaturasSelect().then(cargarHorarios);
