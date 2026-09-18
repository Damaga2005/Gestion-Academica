const asignaturaId = window.ASIGNATURA_ID;
let documentoAbiertoId = null;

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

function mostrarErrorCampo(id, mensaje) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = mensaje
    ? `<svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-circle-alert"></use></svg><span>${escapeHtml(mensaje)}</span>`
    : '';
}

// --- Skeletons de carga inicial ---

function filaEsqueleto() {
  return `
    <div class="detalle-fila">
      <div style="flex:1">
        <div class="ds-skeleton ds-skeleton-title"></div>
        <div class="ds-skeleton ds-skeleton-line"></div>
      </div>
    </div>
  `;
}

function documentosEsqueleto() {
  return `
    <div class="apartado-bloque">
      <div class="ds-skeleton ds-skeleton-title" style="width:180px"></div>
      <div class="ds-skeleton" style="height:84px;margin-top:var(--ds-space-4);border-radius:var(--ds-radius-md)"></div>
    </div>
  `;
}

function mostrarEsqueletos() {
  document.getElementById('evaluacion-lista').innerHTML = filaEsqueleto().repeat(2);
  document.getElementById('recursos-lista').innerHTML = filaEsqueleto().repeat(2);
  document.getElementById('tareas-lista').innerHTML = filaEsqueleto().repeat(2);
  document.getElementById('documentos-explorador').innerHTML = documentosEsqueleto().repeat(2);
}

const ETIQUETA_ESTADO = {
  superada: 'Superada',
  cursando: 'Cursando',
  pendiente: 'Pendiente',
  no_superada: 'No superada',
  no_elegida: 'No elegida',
};
const BADGE_POR_ESTADO = {
  superada: 'ds-badge-success',
  cursando: 'ds-badge-accent',
  pendiente: 'ds-badge',
  no_superada: 'ds-badge-danger',
  no_elegida: 'ds-badge',
};

// "Estado de las Asignaturas" (spec): indicador calculado solo a partir de las
// notas, independiente del estado manual de arriba.
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

// --- Cabecera + Resumen (comparten la misma carga de datos) ---

function progresoDe(asignatura) {
  if (asignatura.estado === 'superada' || asignatura.estado === 'no_superada') return 100;
  if (asignatura.estado === 'cursando') {
    const total = asignatura.componentes.reduce((s, c) => s + c.porcentaje, 0);
    const hecho = asignatura.componentes.filter((c) => c.nota !== null).reduce((s, c) => s + c.porcentaje, 0);
    return total > 0 ? (hecho / total) * 100 : 0;
  }
  return 0;
}

async function cargarCabeceraYResumen() {
  const asignatura = await api(`/asignaturas/${asignaturaId}`);

  document.getElementById('titulo-pagina').textContent = `${asignatura.nombre} · GREELEC`;
  document.getElementById('detalle-nombre').textContent =
    asignatura.siglas ? `${asignatura.siglas} · ${asignatura.nombre}` : asignatura.nombre;
  asignaturaCorta = asignatura.siglas || asignatura.nombre;

  const inputSiglas = document.getElementById('resumen-siglas-input');
  if (document.activeElement !== inputSiglas) {
    inputSiglas.value = asignatura.siglas || '';
  }

  const badge = document.getElementById('detalle-badge-estado');
  badge.textContent = ETIQUETA_ESTADO[asignatura.estado] || asignatura.estado;
  badge.className = `ds-badge ${BADGE_POR_ESTADO[asignatura.estado] || ''}`;

  const badgeNotas = document.getElementById('detalle-badge-estado-notas');
  badgeNotas.textContent = ETIQUETA_ESTADO_NOTAS[asignatura.estado_notas] || '';
  badgeNotas.className = `ds-badge ${BADGE_POR_ESTADO_NOTAS[asignatura.estado_notas] || ''}`;

  document.getElementById('detalle-creditos').textContent =
    `${asignatura.creditos_ects} ECTS · ${asignatura.tipo === 'optativa' ? 'Optativa' : 'Obligatoria'}`;

  const selectEstado = document.getElementById('detalle-select-estado');
  if (['superada', 'cursando', 'pendiente', 'no_superada'].includes(asignatura.estado)) {
    selectEstado.value = asignatura.estado;
  }

  const btnQuitarEleccion = document.getElementById('btn-quitar-eleccion');
  btnQuitarEleccion.style.display =
    (asignatura.tipo === 'optativa' && asignatura.estado !== 'no_elegida') ? '' : 'none';

  // Resumen
  const selectTipo = document.getElementById('resumen-select-tipo');
  if (document.activeElement !== selectTipo) {
    selectTipo.value = asignatura.tipo === 'optativa' ? 'optativa' : 'obligatoria';
  }

  const inputNota = document.getElementById('resumen-nota-input');
  if (document.activeElement !== inputNota) {
    inputNota.value = asignatura.nota_final != null ? asignatura.nota_final : '';
  }

  if (asignatura.prerrequisitos.length > 0) {
    const filaPrerrequisitos = document.getElementById('resumen-fila-prerrequisitos');
    filaPrerrequisitos.style.display = '';
    document.getElementById('resumen-prerrequisitos').innerHTML = asignatura.prerrequisitos.map((p) =>
      `<span class="ds-badge ${BADGE_POR_ESTADO[p.estado] || ''}">${escapeHtml(p.nombre)}</span>`
    ).join('');
  }

  const progreso = progresoDe(asignatura);
  document.getElementById('resumen-progreso-texto').textContent =
    asignatura.estado === 'cursando' ? `Progreso · ${Math.round(progreso)}% evaluado` : 'Progreso';
  document.getElementById('resumen-progreso-barra').style.width = `${progreso}%`;

  cargarCurso(asignatura.cuatrimestre_id);
  renderEvaluacionAsignatura(asignatura);
  renderRecursos(asignatura.recursos_externos);
  renderProfesores(asignatura.profesores);

  const notasTextarea = document.getElementById('notas-rapidas');
  if (document.activeElement !== notasTextarea) {
    notasTextarea.value = asignatura.notas || '';
  }

  return asignatura;
}

async function cargarCurso(cuatrimestreId) {
  try {
    const cuatrimestre = await api(`/cuatrimestres/${cuatrimestreId}`);
    const anio = await api(`/anios/${cuatrimestre.anio_id}`);
    document.getElementById('resumen-curso').textContent = `Año ${anio.numero} · Cuatrimestre ${cuatrimestre.numero}`;
  } catch (err) {
    document.getElementById('resumen-curso').textContent = '—';
  }
}

// --- Siglas (autoguardado, igual que los campos de profesor) ---

(function () {
  const input = document.getElementById('resumen-siglas-input');
  const error = document.getElementById('resumen-siglas-error');
  const estado = document.getElementById('resumen-siglas-estado');
  let timer = null;

  input.addEventListener('input', () => {
    estado.textContent = '';
    mostrarErrorCampo('resumen-siglas-error', '');
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        const asignatura = await api(`/asignaturas/${asignaturaId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ siglas: input.value.trim() || null }),
        });
        input.value = asignatura.siglas || '';
        document.getElementById('detalle-nombre').textContent =
          asignatura.siglas ? `${asignatura.siglas} · ${asignatura.nombre}` : asignatura.nombre;
        estado.textContent = 'Guardado ✓';
        setTimeout(() => { estado.textContent = ''; }, 2000);
      } catch (err) {
        mostrarErrorCampo('resumen-siglas-error', err.message);
      }
    }, 600);
  });
})();

// --- Nota final (autoguardado, para colgarla directamente sin desglose) ---

(function () {
  const input = document.getElementById('resumen-nota-input');
  const error = document.getElementById('resumen-nota-error');
  const estado = document.getElementById('resumen-nota-estado');
  let timer = null;

  input.addEventListener('input', () => {
    estado.textContent = '';
    mostrarErrorCampo('resumen-nota-error', '');

    if (input.value && !input.validity.valid) {
      mostrarErrorCampo('resumen-nota-error', 'Indica un número entre 0 y 10.');
      clearTimeout(timer);
      return;
    }

    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        await api(`/asignaturas/${asignaturaId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ nota_final: input.value === '' ? null : Number(input.value) }),
        });
        estado.textContent = 'Guardado ✓';
        setTimeout(() => { estado.textContent = ''; }, 2000);
      } catch (err) {
        mostrarErrorCampo('resumen-nota-error', err.message);
      }
    }, 600);
  });
})();

document.getElementById('detalle-select-estado').addEventListener('change', async (e) => {
  await api(`/api/asignaturas/${asignaturaId}/estado`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ estado: e.target.value }),
  });
  await cargarCabeceraYResumen();
});

document.getElementById('resumen-select-tipo').addEventListener('change', async (e) => {
  try {
    await api(`/asignaturas/${asignaturaId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tipo: e.target.value }),
    });
    mostrarToast('Tipo actualizado', 'success');
    await cargarCabeceraYResumen();
  } catch (err) {
    mostrarToast('Error al actualizar el tipo: ' + err.message, 'danger');
  }
});

document.getElementById('btn-quitar-eleccion').addEventListener('click', async () => {
  const nombre = document.getElementById('detalle-nombre').textContent;
  if (!confirm(`¿Quitar la elección de "${nombre}"? Si viene del catálogo volverá a estar disponible como optativa por elegir. Si la creaste a mano se eliminará por completo.`)) return;
  const meta = document.querySelector('meta[name="csrf-token"]');
  const res = await fetch(`/asignaturas/${asignaturaId}/quitar-eleccion`, {
    method: 'POST',
    headers: { 'X-CSRFToken': meta ? meta.content : '' },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    alert('Error: ' + (data.error || res.status));
    return;
  }
  if (res.status === 204) {
    window.location.href = '/vista';
    return;
  }
  mostrarToast('Elección retirada', 'success');
  await cargarCabeceraYResumen();
});

document.getElementById('btn-borrar-asignatura').addEventListener('click', async () => {
  const nombre = document.getElementById('detalle-nombre').textContent;
  if (!confirm(`¿Eliminar la asignatura "${nombre}"? Esta acción no se puede deshacer.`)) return;
  await api(`/asignaturas/${asignaturaId}`, { method: 'DELETE' });
  window.location.href = '/vista';
});

// --- Profesorado ---

let profesoresCache = [];

function filaProfesorVista(p) {
  return `
    <div class="detalle-fila" data-id="${p.id}">
      <div class="recurso-fila-icono">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-graduation-cap"></use></svg>
      </div>
      <div class="recurso-fila-info">
        <span class="ds-body">${escapeHtml(p.nombre)}</span>
        ${p.rol ? `<p class="ds-caption">${escapeHtml(p.rol)}</p>` : ''}
        ${p.despacho ? `<p class="ds-caption">${escapeHtml(p.despacho)}</p>` : ''}
      </div>
      <div class="fila-acciones">
        ${p.correo ? `
        <a class="fila-icono-btn" href="mailto:${escapeHtml(p.correo)}" title="Enviar email">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-mail"></use></svg>
        </a>` : ''}
        ${p.aula_virtual ? `
        <a class="fila-icono-btn" href="${escapeHtml(p.aula_virtual)}" target="_blank" rel="noopener" title="Abrir aula virtual">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-external-link"></use></svg>
        </a>` : ''}
        <button type="button" class="fila-icono-btn btn-editar-profesor" title="Editar">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-pencil"></use></svg>
        </button>
        <button type="button" class="fila-icono-btn btn-borrar-profesor" title="Eliminar">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
        </button>
      </div>
    </div>
  `;
}

function filaProfesorEdicion(p) {
  return `
    <div class="detalle-fila detalle-fila-edicion" data-id="${p.id}">
      <form class="detalle-form-anadir form-editar-profesor">
        <div class="ds-field">
          <label class="ds-label">Nombre</label>
          <input type="text" class="ds-input campo-editar-nombre" value="${escapeHtml(p.nombre)}" required>
        </div>
        <div class="ds-field" style="flex-basis:160px">
          <label class="ds-label">Rol / grupos</label>
          <input type="text" class="ds-input campo-editar-rol" value="${escapeHtml(p.rol || '')}">
        </div>
        <div class="ds-field">
          <label class="ds-label">Correo</label>
          <input type="email" class="ds-input campo-editar-correo" value="${escapeHtml(p.correo || '')}">
        </div>
        <div class="ds-field">
          <label class="ds-label">Despacho</label>
          <input type="text" class="ds-input campo-editar-despacho" value="${escapeHtml(p.despacho || '')}">
        </div>
        <div class="ds-field">
          <label class="ds-label">Aula virtual</label>
          <input type="url" class="ds-input campo-editar-aula" value="${escapeHtml(p.aula_virtual || '')}">
        </div>
        <button type="submit" class="ds-btn ds-btn-secondary">Guardar</button>
        <button type="button" class="ds-btn ds-btn-secondary btn-cancelar-edicion-profesor">Cancelar</button>
      </form>
      <p class="ds-field-error campo-editar-error"></p>
    </div>
  `;
}

function renderProfesores(profesores) {
  profesoresCache = profesores || [];
  const contenedor = document.getElementById('profesores-lista');
  if (profesoresCache.length === 0) {
    contenedor.innerHTML = '<p class="sin-elementos">Sin profesorado todavía.</p>';
    return;
  }

  contenedor.innerHTML = profesoresCache.map(filaProfesorVista).join('');
  reanimar(contenedor);

  contenedor.querySelectorAll('.btn-borrar-profesor').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.closest('.detalle-fila').dataset.id;
      if (!confirm('¿Eliminar este profesor?')) return;
      await api(`/profesores/${id}`, { method: 'DELETE' });
      await cargarCabeceraYResumen();
      mostrarToast('Profesor eliminado', 'success');
    });
  });

  contenedor.querySelectorAll('.btn-editar-profesor').forEach((btn) => {
    btn.addEventListener('click', () => {
      const fila = btn.closest('.detalle-fila');
      const id = Number(fila.dataset.id);
      const profesor = profesoresCache.find((p) => p.id === id);
      if (!profesor) return;
      fila.outerHTML = filaProfesorEdicion(profesor);
      const nuevaFila = contenedor.querySelector(`.detalle-fila-edicion[data-id="${id}"]`);
      reanimar(nuevaFila);

      nuevaFila.querySelector('.btn-cancelar-edicion-profesor').addEventListener('click', () => {
        nuevaFila.outerHTML = filaProfesorVista(profesor);
        reanimar(contenedor.querySelector(`.detalle-fila[data-id="${id}"]`));
      });

      nuevaFila.querySelector('.form-editar-profesor').addEventListener('submit', async (e) => {
        e.preventDefault();
        const nombre = nuevaFila.querySelector('.campo-editar-nombre').value.trim();
        const correoInput = nuevaFila.querySelector('.campo-editar-correo');
        const errorEl = nuevaFila.querySelector('.campo-editar-error');
        errorEl.textContent = '';
        if (!nombre) {
          errorEl.textContent = 'Indica un nombre.';
          return;
        }
        if (correoInput.value && !correoInput.validity.valid) {
          errorEl.textContent = 'Ese correo no tiene un formato válido.';
          return;
        }
        const boton = e.submitter || e.target.querySelector('button[type="submit"]');
        boton.classList.add('is-loading');
        try {
          await api(`/profesores/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              nombre,
              rol: nuevaFila.querySelector('.campo-editar-rol').value.trim() || null,
              correo: correoInput.value.trim() || null,
              despacho: nuevaFila.querySelector('.campo-editar-despacho').value.trim() || null,
              aula_virtual: nuevaFila.querySelector('.campo-editar-aula').value.trim() || null,
            }),
          });
          await cargarCabeceraYResumen();
          mostrarToast('Profesor actualizado', 'success');
        } catch (err) {
          errorEl.textContent = err.message;
        } finally {
          boton.classList.remove('is-loading');
        }
      });
    });
  });
}

document.getElementById('form-nuevo-profesor').addEventListener('submit', async (e) => {
  e.preventDefault();
  mostrarErrorCampo('profesor-error', '');
  const nombre = document.getElementById('profesor-nombre').value.trim();
  const correoInput = document.getElementById('profesor-correo');
  if (!nombre) {
    mostrarErrorCampo('profesor-error', 'Indica un nombre.');
    return;
  }
  if (correoInput.value && !correoInput.validity.valid) {
    mostrarErrorCampo('profesor-error', 'Ese correo no tiene un formato válido.');
    return;
  }
  const boton = e.submitter || e.target.querySelector('button[type="submit"]');
  boton.classList.add('is-loading');
  try {
    await api(`/asignaturas/${asignaturaId}/profesores`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nombre,
        rol: document.getElementById('profesor-rol').value.trim() || null,
        correo: correoInput.value.trim() || null,
        despacho: document.getElementById('profesor-despacho').value.trim() || null,
        aula_virtual: document.getElementById('profesor-aula-virtual').value.trim() || null,
      }),
    });
    e.target.reset();
    await cargarCabeceraYResumen();
  } catch (err) {
    mostrarErrorCampo('profesor-error', err.message);
  } finally {
    boton.classList.remove('is-loading');
  }
});

// --- Evaluación ---

const ETIQUETA_TIPO_COMPONENTE = {
  teoria: 'Teoría', parcial: 'Parcial', examen_final: 'Examen final', laboratorio: 'Laboratorio', otro: 'Otro',
};

// Esquema único activo en pantalla (para el formulario "+ Añadir bloque", que
// necesita saber a qué esquema añadirlo). null si la asignatura no tiene ninguno
// todavía (caso raro: la ruta histórica /asignaturas/<id>/componentes crea uno sobre
// la marcha en cuanto se añade el primer componente).
let esquemaUnicoId = null;

// Orquestador: decide entre la vista de un único esquema (igual que siempre) y la
// vista de comparación lado a lado (solo cuando hay más de un EsquemaEvaluacion).
function renderEvaluacionAsignatura(asignatura) {
  const esquemas = asignatura.esquemas || [];
  const comparando = esquemas.length > 1;

  document.getElementById('evaluacion-unico').style.display = comparando ? 'none' : '';
  document.getElementById('evaluacion-comparacion').style.display = comparando ? '' : 'none';

  if (comparando) {
    esquemaUnicoId = null;
    renderComparacionEsquemas(esquemas);
  } else if (esquemas.length === 1) {
    esquemaUnicoId = esquemas[0].id;
    renderEvaluacion(esquemas[0]);
  } else {
    // Sin ningún esquema todavía (raro: solo asignaturas migradas de antes de la
    // fase de esquemas múltiples): sus componentes cuelgan directo de la asignatura,
    // sin bloques posibles (bloque_id exige un esquema_id).
    esquemaUnicoId = null;
    renderEvaluacion({ componentes: asignatura.componentes, componentes_efectivos: asignatura.componentes, bloques: [] });
  }
}

// --- Calculadora "qué nota necesito sacar en lo que falta" (reutilizable por esquema) ---

function calcularNotaNecesaria(componentes, objetivo) {
  const pesoTotal = componentes.reduce((s, c) => s + c.porcentaje, 0);
  if (pesoTotal <= 0) return { estado: 'sin-componentes' };

  const conNota = componentes.filter((c) => c.nota !== null);
  const pesoHecho = conNota.reduce((s, c) => s + c.porcentaje, 0);
  const pesoFaltante = pesoTotal - pesoHecho;
  if (pesoFaltante <= 0) return { estado: 'completo' };

  const sumaHecho = conNota.reduce((s, c) => s + c.porcentaje * c.nota, 0);
  const notaNecesaria = (objetivo * pesoTotal - sumaHecho) / pesoFaltante;
  return { estado: 'ok', notaNecesaria, pesoFaltante };
}

function textoNotaNecesaria(resultado) {
  if (resultado.estado === 'sin-componentes') return 'Añade componentes de evaluación para poder calcularlo.';
  if (resultado.estado === 'completo') return 'Ya tienes nota en todo el peso de este esquema.';
  const { notaNecesaria, pesoFaltante } = resultado;
  if (notaNecesaria <= 0) return `Objetivo ya asegurado (te vale hasta un 0 en el ${pesoFaltante}% restante).`;
  if (notaNecesaria > 10) return `Con las notas actuales no es posible alcanzar ese objetivo (necesitarías más de un 10 en el ${pesoFaltante}% restante).`;
  return `Necesitas sacar de media al menos un ${notaNecesaria.toFixed(2)} en el ${pesoFaltante}% que falta.`;
}

// --- Comparación de esquemas (lado a lado) ---

function renderComparacionEsquemas(esquemas) {
  const contenedor = document.getElementById('evaluacion-comparacion');

  contenedor.innerHTML = esquemas.map((esquema) => {
    const r = esquema.resultado;
    return `
    <div class="esquema-card ${esquema.aplicado ? 'is-aplicado' : ''}" data-esquema-id="${esquema.id}">
      <div class="esquema-card-header">
        <h3 class="ds-h3">${escapeHtml(esquema.nombre)}</h3>
        ${esquema.aplicado ? '<span class="ds-badge ds-badge-success">Se aplicaría</span>' : ''}
        <button type="button" class="fila-icono-btn btn-duplicar-esquema" title="Duplicar esquema (sin notas)">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-copy"></use></svg>
        </button>
        <button type="button" class="fila-icono-btn btn-borrar-esquema" title="Eliminar esquema">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
        </button>
      </div>

      <div class="evaluacion-resumen">
        <div>
          <p class="ds-caption">Evaluado</p>
          <p class="evaluacion-stat-numero">${r.porcentaje_evaluado}%</p>
        </div>
        <div>
          <p class="ds-caption">Nota media ponderada</p>
          <p class="evaluacion-stat-numero">${r.media_ponderada != null ? r.media_ponderada.toFixed(2) : '—'}</p>
        </div>
      </div>

      <div class="esquema-componentes-lista">
        ${(esquema.componentes.length === 0 && esquema.bloques.length === 0) ? '<p class="sin-elementos">Sin componentes todavía.</p>' : ''}
        ${esquema.componentes.map(filaComponenteHtml).join('')}
        ${esquema.bloques.map(filaBloqueHtml).join('')}
        ${avisoSumaHtml(esquema.componentes_efectivos)}
      </div>

      <form class="detalle-form-anadir form-nuevo-componente-esquema">
        <div class="ds-field">
          <label class="ds-label">Nombre</label>
          <input type="text" class="ds-input campo-nombre-nuevo" placeholder="Ej. Parcial 1" required>
        </div>
        <div class="ds-field" style="flex-basis:130px">
          <label class="ds-label">Tipo</label>
          <select class="ds-select campo-tipo-nuevo">
            <option value="teoria">Teoría</option>
            <option value="parcial">Parcial</option>
            <option value="examen_final">Examen final</option>
            <option value="laboratorio">Laboratorio</option>
            <option value="otro">Otro</option>
          </select>
        </div>
        <div class="ds-field" style="flex-basis:90px">
          <label class="ds-label">% peso</label>
          <input type="number" class="ds-input campo-porcentaje-nuevo" min="0" max="100" step="0.01" required>
        </div>
        <button type="submit" class="ds-btn ds-btn-secondary">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-plus"></use></svg>
          Añadir
        </button>
      </form>

      <form class="detalle-form-anadir form-nuevo-bloque-esquema">
        <div class="ds-field">
          <input type="text" class="ds-input campo-nombre-bloque-nuevo" placeholder="Nombre del bloque" required>
        </div>
        <div class="ds-field" style="flex-basis:90px">
          <input type="number" class="ds-input campo-porcentaje-bloque-nuevo" min="0" max="100" step="0.01" placeholder="% peso" required>
        </div>
        <button type="submit" class="ds-btn ds-btn-secondary">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-plus"></use></svg>
          Añadir bloque
        </button>
      </form>

      <div class="esquema-calculadora">
        <div class="ds-field">
          <label class="ds-label">¿Qué nota necesito? Objetivo</label>
          <input type="number" class="ds-input campo-objetivo-esquema" min="0" max="10" step="0.1" value="5">
        </div>
        <p class="ds-caption esquema-calculadora-resultado"></p>
      </div>
    </div>
  `;
  }).join('');
  reanimar(contenedor);

  contenedor.querySelectorAll('.esquema-card').forEach((tarjeta) => {
    const esquemaId = tarjeta.dataset.esquemaId;
    const esquema = esquemas.find((e) => String(e.id) === esquemaId);

    const actualizarCalculadora = () => {
      const objetivo = parseFloat(tarjeta.querySelector('.campo-objetivo-esquema').value);
      const resultado = calcularNotaNecesaria(esquema.componentes_efectivos, Number.isNaN(objetivo) ? 5 : objetivo);
      tarjeta.querySelector('.esquema-calculadora-resultado').textContent = textoNotaNecesaria(resultado);
    };
    actualizarCalculadora();
    tarjeta.querySelector('.campo-objetivo-esquema').addEventListener('input', actualizarCalculadora);

    tarjeta.querySelector('.btn-duplicar-esquema').addEventListener('click', async () => {
      try {
        await api(`/esquemas/${esquemaId}/duplicar`, { method: 'POST' });
        mostrarToast('Esquema duplicado', 'success');
        await cargarCabeceraYResumen();
      } catch (err) {
        mostrarToast(err.message, 'danger');
      }
    });

    tarjeta.querySelector('.btn-borrar-esquema').addEventListener('click', async () => {
      if (!confirm(`¿Eliminar el esquema "${esquema.nombre}" y todos sus componentes? Esta acción no se puede deshacer.`)) return;
      const meta = document.querySelector('meta[name="csrf-token"]');
      const res = await fetch(`/esquemas/${esquemaId}`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': meta ? meta.content : '' },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        mostrarToast(data.error || 'No se pudo eliminar el esquema', 'danger');
        return;
      }
      mostrarToast('Esquema eliminado', 'success');
      await cargarCabeceraYResumen();
    });

    activarEventosEvaluacion(tarjeta.querySelector('.esquema-componentes-lista'), cargarCabeceraYResumen);

    tarjeta.querySelector('.form-nuevo-bloque-esquema').addEventListener('submit', async (e) => {
      e.preventDefault();
      const nombre = tarjeta.querySelector('.campo-nombre-bloque-nuevo').value.trim();
      const porcentaje = parseFloat(tarjeta.querySelector('.campo-porcentaje-bloque-nuevo').value);
      if (!nombre || Number.isNaN(porcentaje)) return;
      const boton = e.target.querySelector('button[type="submit"]');
      boton.classList.add('is-loading');
      try {
        await api(`/esquemas/${esquemaId}/bloques`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ nombre, porcentaje }),
        });
        await cargarCabeceraYResumen();
      } catch (err) {
        mostrarToast(err.message, 'danger');
      } finally {
        boton.classList.remove('is-loading');
      }
    });

    tarjeta.querySelector('.form-nuevo-componente-esquema').addEventListener('submit', async (e) => {
      e.preventDefault();
      const nombre = tarjeta.querySelector('.campo-nombre-nuevo').value.trim();
      const tipo = tarjeta.querySelector('.campo-tipo-nuevo').value;
      const porcentaje = parseFloat(tarjeta.querySelector('.campo-porcentaje-nuevo').value);
      if (!nombre || Number.isNaN(porcentaje)) return;
      const boton = e.target.querySelector('button[type="submit"]');
      boton.classList.add('is-loading');
      try {
        await api(`/esquemas/${esquemaId}/componentes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ nombre, tipo, porcentaje }),
        });
        await cargarCabeceraYResumen();
      } catch (err) {
        mostrarToast(err.message, 'danger');
      } finally {
        boton.classList.remove('is-loading');
      }
    });
  });
}

document.getElementById('btn-anadir-esquema').addEventListener('click', async () => {
  if (esquemaUnicoId && confirm('¿Partir de una copia del esquema actual (mismos componentes y pesos, sin notas)?\n\nAceptar = copiar · Cancelar = esquema vacío')) {
    try {
      await api(`/esquemas/${esquemaUnicoId}/duplicar`, { method: 'POST' });
      mostrarToast('Esquema duplicado', 'success');
      await cargarCabeceraYResumen();
    } catch (err) {
      mostrarToast(err.message, 'danger');
    }
    return;
  }
  const nombre = prompt('Nombre del nuevo esquema (ej. "Fórmula alternativa"):');
  if (!nombre || !nombre.trim()) return;
  try {
    await api(`/asignaturas/${asignaturaId}/esquemas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre: nombre.trim() }),
    });
    mostrarToast('Esquema añadido', 'success');
    await cargarCabeceraYResumen();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
});

// --- Bloques de evaluación (nota jerárquica: un grupo cuya propia nota sale de sus
// propios componentes, ej. Laboratorio = 40% calculado a partir de prácticas/control).
// Helpers compartidos entre la vista de un único esquema y cada tarjeta de comparación.

// Aviso si los pesos de una lista de componentes (o de un esquema) no suman 100%.
function avisoSumaHtml(items) {
  if (items.length === 0) return '';
  const suma = Math.round(items.reduce((s, c) => s + c.porcentaje, 0) * 100) / 100;
  if (suma === 100) return '';
  return `<p class="ds-caption aviso-suma" style="color:var(--ds-warning, #b7791f)">Los pesos suman ${suma}% (deberían sumar 100%).</p>`;
}

// Pide nombre y % con prompt() y los guarda con PUT; cancelar o dejar vacío = no cambiar.
// `minimoActual` solo se pasa para componentes (undefined = los bloques no tienen mínimo).
async function editarNombreYPorcentaje(url, nombreActual, porcentajeActual, minimoActual) {
  const nombre = prompt('Nombre:', nombreActual);
  if (nombre === null) return false;
  const texto = prompt('% de peso:', String(porcentajeActual));
  if (texto === null) return false;
  const porcentaje = parseFloat(texto.replace(',', '.'));
  if (!nombre.trim() || Number.isNaN(porcentaje)) {
    mostrarToast('Indica un nombre y un porcentaje válido', 'danger');
    return false;
  }
  const cuerpo = { nombre: nombre.trim(), porcentaje };
  if (minimoActual !== undefined) {
    const textoMin = prompt('Nota mínima para aprobar (vacío = sin mínimo):', minimoActual);
    if (textoMin === null) return false;
    const minimo = textoMin.trim() === '' ? null : parseFloat(textoMin.replace(',', '.'));
    if (Number.isNaN(minimo)) {
      mostrarToast('La nota mínima no es válida', 'danger');
      return false;
    }
    cuerpo.nota_minima = minimo;
  }
  await api(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) });
  return true;
}

function filaComponenteHtml(c) {
  return `
    <div class="detalle-fila" data-id="${c.id}" data-nombre="${escapeHtml(c.nombre)}" data-porcentaje="${c.porcentaje}" data-minimo="${c.nota_minima ?? ''}">
      <div class="evaluacion-fila-nombre">
        <span class="ds-body">${escapeHtml(c.nombre)}</span>
        <p class="ds-caption">${ETIQUETA_TIPO_COMPONENTE[c.tipo] || c.tipo} · ${c.porcentaje}%${c.nota_minima != null ? ` · mín. ${c.nota_minima}` : ''}${c.nota_minima != null && c.nota != null && c.nota < c.nota_minima ? ' <strong style="color:var(--ds-danger, #c0392b)">⚠ por debajo del mínimo</strong>' : ''}</p>
      </div>
      <input type="number" class="ds-input evaluacion-fila-nota campo-nota" step="0.01" placeholder="Nota" value="${c.nota ?? ''}">
      <div class="fila-acciones">
        <button type="button" class="fila-icono-btn btn-editar-eval" title="Editar nombre y peso" aria-label="Editar">✎</button>
        <button type="button" class="fila-icono-btn btn-mover" data-dir="arriba" title="Subir" aria-label="Subir">▲</button>
        <button type="button" class="fila-icono-btn btn-mover" data-dir="abajo" title="Bajar" aria-label="Bajar">▼</button>
        <button type="button" class="fila-icono-btn btn-borrar-componente" title="Eliminar">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
        </button>
      </div>
    </div>
  `;
}

// Bloques desplegados por el usuario: se conservan al recargar tras subir/bajar filas.
const bloquesExpandidos = new Set();

function filaBloqueHtml(b) {
  const nota = b.resultado.media_ponderada;
  const abierto = bloquesExpandidos.has(String(b.id));
  return `
    <div class="evaluacion-bloque" data-bloque-id="${b.id}" data-bloque-nombre="${escapeHtml(b.nombre)}" data-bloque-porcentaje="${b.porcentaje}">
      <div class="detalle-fila evaluacion-fila-bloque">
        <button type="button" class="evaluacion-bloque-toggle ${abierto ? 'is-expandido' : ''}" aria-expanded="${abierto}" title="Ver componentes del bloque">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-chevron-right"></use></svg>
        </button>
        <div class="evaluacion-fila-nombre">
          <span class="ds-body">${escapeHtml(b.nombre)} <span class="ds-badge ds-badge-accent">Bloque</span></span>
          <p class="ds-caption">${b.porcentaje}% de la nota final · ${b.resultado.porcentaje_evaluado}% evaluado</p>
        </div>
        <span class="evaluacion-fila-nota-calculada" data-tooltip="Nota calculada a partir de sus componentes">${nota != null ? nota.toFixed(2) : '—'}</span>
        <div class="fila-acciones">
          <button type="button" class="fila-icono-btn btn-editar-eval" title="Editar nombre y peso" aria-label="Editar">✎</button>
        <button type="button" class="fila-icono-btn btn-mover" data-dir="arriba" title="Subir" aria-label="Subir">▲</button>
        <button type="button" class="fila-icono-btn btn-mover" data-dir="abajo" title="Bajar" aria-label="Bajar">▼</button>
        <button type="button" class="fila-icono-btn btn-borrar-bloque" title="Eliminar bloque">
            <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
          </button>
        </div>
      </div>
      <div class="evaluacion-bloque-sub" ${abierto ? '' : 'hidden'}>
        ${b.componentes.length === 0 ? '<p class="sin-elementos">Sin componentes en este bloque todavía.</p>' : b.componentes.map(filaComponenteHtml).join('')}
        ${avisoSumaHtml(b.componentes)}
        <form class="detalle-form-anadir form-nuevo-componente-bloque">
          <div class="ds-field">
            <input type="text" class="ds-input campo-nombre-sub" placeholder="Nombre del componente" required>
          </div>
          <div class="ds-field" style="flex-basis:90px">
            <input type="number" class="ds-input campo-porcentaje-sub" min="0" max="100" step="0.01" placeholder="% del bloque" required>
          </div>
          <button type="submit" class="ds-btn ds-btn-secondary">
            <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-plus"></use></svg>
            Añadir
          </button>
        </form>
      </div>
    </div>
  `;
}

// Engancha los eventos de todas las filas (sueltas y de bloque, con sus sub-filas)
// dentro de `contenedor`. `onCambio` se llama tras cualquier cambio que afecte a
// notas/estructura (recarga toda la asignatura, igual que hacía cada listener suelto
// antes de esta refactorización).
function activarEventosEvaluacion(contenedor, onCambio) {
  contenedor.querySelectorAll('.detalle-fila:not(.evaluacion-fila-bloque)').forEach((fila) => {
    const id = fila.dataset.id;
    fila.querySelector('.campo-nota').addEventListener('change', async (e) => {
      const valor = e.target.value.trim();
      await api(`/componentes/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nota: valor === '' ? null : parseFloat(valor) }),
      });
      await onCambio();
    });
    fila.querySelector('.btn-editar-eval').addEventListener('click', async () => {
      if (await editarNombreYPorcentaje(`/componentes/${id}`, fila.dataset.nombre, fila.dataset.porcentaje, fila.dataset.minimo)) await onCambio();
    });
    fila.querySelectorAll('.btn-mover').forEach((b) => b.addEventListener('click', async () => {
      await api(`/componentes/${id}/mover`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ direccion: b.dataset.dir }),
      });
      await onCambio();
    }));
    fila.querySelector('.btn-borrar-componente').addEventListener('click', async () => {
      if (!confirm('¿Eliminar este componente de evaluación? Esta acción no se puede deshacer.')) return;
      await api(`/componentes/${id}`, { method: 'DELETE' });
      await onCambio();
      mostrarToast('Componente eliminado', 'success');
    });
  });

  contenedor.querySelectorAll('.evaluacion-bloque').forEach((bloqueEl) => {
    const bloqueId = bloqueEl.dataset.bloqueId;
    const boton = bloqueEl.querySelector('.evaluacion-bloque-toggle');
    const sub = bloqueEl.querySelector('.evaluacion-bloque-sub');
    boton.addEventListener('click', () => {
      sub.hidden = !sub.hidden;
      boton.setAttribute('aria-expanded', String(!sub.hidden));
      boton.classList.toggle('is-expandido', !sub.hidden);
      if (sub.hidden) bloquesExpandidos.delete(bloqueId); else bloquesExpandidos.add(bloqueId);
    });
    bloqueEl.querySelector('.evaluacion-fila-bloque .btn-editar-eval').addEventListener('click', async () => {
      if (await editarNombreYPorcentaje(`/bloques/${bloqueId}`, bloqueEl.dataset.bloqueNombre, bloqueEl.dataset.bloquePorcentaje)) await onCambio();
    });
    bloqueEl.querySelectorAll('.evaluacion-fila-bloque .btn-mover').forEach((b) => b.addEventListener('click', async () => {
      await api(`/bloques/${bloqueId}/mover`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ direccion: b.dataset.dir }),
      });
      await onCambio();
    }));
    bloqueEl.querySelector('.btn-borrar-bloque').addEventListener('click', async () => {
      if (!confirm(`¿Eliminar el bloque "${bloqueEl.dataset.bloqueNombre}" y todos sus componentes? Esta acción no se puede deshacer.`)) return;
      await api(`/bloques/${bloqueId}`, { method: 'DELETE' });
      await onCambio();
      mostrarToast('Bloque eliminado', 'success');
    });
    bloqueEl.querySelector('.form-nuevo-componente-bloque').addEventListener('submit', async (e) => {
      e.preventDefault();
      const nombre = e.target.querySelector('.campo-nombre-sub').value.trim();
      const porcentaje = parseFloat(e.target.querySelector('.campo-porcentaje-sub').value);
      if (!nombre || Number.isNaN(porcentaje)) return;
      const boton = e.target.querySelector('button[type="submit"]');
      boton.classList.add('is-loading');
      try {
        await api(`/bloques/${bloqueId}/componentes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ nombre, porcentaje }),
        });
        await onCambio();
      } catch (err) {
        mostrarToast(err.message, 'danger');
      } finally {
        boton.classList.remove('is-loading');
      }
    });
  });
}

function renderEvaluacion(esquema) {
  const contenedor = document.getElementById('evaluacion-lista');
  const efectivos = esquema.componentes_efectivos;
  const totalPeso = efectivos.reduce((s, c) => s + c.porcentaje, 0);
  const pesoEvaluado = efectivos.filter((c) => c.nota !== null).reduce((s, c) => s + c.porcentaje, 0);
  const porcentajeEvaluado = totalPeso > 0 ? Math.round((pesoEvaluado / totalPeso) * 100) : 0;
  document.getElementById('evaluacion-porcentaje').textContent = `${porcentajeEvaluado}%`;

  const conNota = efectivos.filter((c) => c.nota !== null);
  const mediaWrap = document.getElementById('evaluacion-media-wrap');
  if (conNota.length > 0) {
    const pesoConNota = conNota.reduce((s, c) => s + c.porcentaje, 0);
    const media = pesoConNota > 0
      ? conNota.reduce((s, c) => s + c.porcentaje * c.nota, 0) / pesoConNota
      : 0;
    document.getElementById('evaluacion-media').textContent = media.toFixed(2);
    mediaWrap.style.display = '';
  } else {
    mediaWrap.style.display = 'none';
  }

  const calculadora = document.getElementById('evaluacion-calculadora');
  if (efectivos.length === 0) {
    contenedor.innerHTML = '<p class="sin-elementos">Sin componentes de evaluación todavía.</p>';
    calculadora.style.display = 'none';
    return;
  }
  calculadora.style.display = '';
  const objetivoInput = document.getElementById('evaluacion-objetivo');
  const actualizarCalculadora = () => {
    const objetivo = parseFloat(objetivoInput.value);
    const resultado = calcularNotaNecesaria(efectivos, Number.isNaN(objetivo) ? 5 : objetivo);
    document.getElementById('evaluacion-calculadora-resultado').textContent = textoNotaNecesaria(resultado);
  };
  actualizarCalculadora();
  objetivoInput.oninput = actualizarCalculadora;

  contenedor.innerHTML =
    esquema.componentes.map(filaComponenteHtml).join('') + esquema.bloques.map(filaBloqueHtml).join('') + avisoSumaHtml(efectivos);
  reanimar(contenedor);
  activarEventosEvaluacion(contenedor, cargarCabeceraYResumen);
}

document.getElementById('form-nuevo-componente').addEventListener('submit', async (e) => {
  e.preventDefault();
  mostrarErrorCampo('componente-error', '');
  const nombre = document.getElementById('componente-nombre').value.trim();
  const tipo = document.getElementById('componente-tipo').value;
  const porcentaje = parseFloat(document.getElementById('componente-porcentaje').value);
  if (!nombre || Number.isNaN(porcentaje)) {
    mostrarErrorCampo('componente-error', 'Indica un nombre y un porcentaje válido.');
    return;
  }
  const boton = e.submitter || e.target.querySelector('button[type="submit"]');
  boton.classList.add('is-loading');
  try {
    await api(`/asignaturas/${asignaturaId}/componentes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre, tipo, porcentaje }),
    });
    e.target.reset();
    await cargarCabeceraYResumen();
  } catch (err) {
    mostrarErrorCampo('componente-error', err.message);
  } finally {
    boton.classList.remove('is-loading');
  }
});

document.getElementById('form-nuevo-bloque').addEventListener('submit', async (e) => {
  e.preventDefault();
  mostrarErrorCampo('bloque-error', '');
  const nombre = document.getElementById('bloque-nombre').value.trim();
  const porcentaje = parseFloat(document.getElementById('bloque-porcentaje').value);
  if (!nombre || Number.isNaN(porcentaje)) {
    mostrarErrorCampo('bloque-error', 'Indica un nombre y un porcentaje válido.');
    return;
  }
  if (!esquemaUnicoId) {
    mostrarErrorCampo('bloque-error', 'Añade primero un componente normal (crea el esquema de evaluación) antes de poder añadir un bloque.');
    return;
  }
  const boton = e.submitter || e.target.querySelector('button[type="submit"]');
  boton.classList.add('is-loading');
  try {
    await api(`/esquemas/${esquemaUnicoId}/bloques`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre, porcentaje }),
    });
    e.target.reset();
    await cargarCabeceraYResumen();
  } catch (err) {
    mostrarErrorCampo('bloque-error', err.message);
  } finally {
    boton.classList.remove('is-loading');
  }
});

// --- Recursos ---

function renderRecursos(recursos) {
  const contenedor = document.getElementById('recursos-lista');
  if (recursos.length === 0) {
    contenedor.innerHTML = '<p class="sin-elementos">Sin recursos todavía.</p>';
    return;
  }

  contenedor.innerHTML = recursos.map((r) => `
    <div class="detalle-fila" data-id="${r.id}">
      <div class="recurso-fila-icono">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-external-link"></use></svg>
      </div>
      <div class="recurso-fila-info">
        <span class="ds-body">${escapeHtml(r.nombre)}</span>
        ${r.tipo ? `<p class="ds-caption">${escapeHtml(r.tipo)}</p>` : ''}
      </div>
      <div class="fila-acciones">
        <a class="fila-icono-btn" href="${escapeHtml(r.url)}" target="_blank" rel="noopener" title="Abrir">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-external-link"></use></svg>
        </a>
        <button type="button" class="fila-icono-btn btn-borrar-recurso" title="Eliminar">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
        </button>
      </div>
    </div>
  `).join('');
  reanimar(contenedor);

  contenedor.querySelectorAll('.btn-borrar-recurso').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.closest('.detalle-fila').dataset.id;
      if (!confirm('¿Eliminar este recurso?')) return;
      await api(`/recursos-externos/${id}`, { method: 'DELETE' });
      await cargarCabeceraYResumen();
      mostrarToast('Recurso eliminado', 'success');
    });
  });
}

document.getElementById('form-nuevo-recurso').addEventListener('submit', async (e) => {
  e.preventDefault();
  mostrarErrorCampo('recurso-error', '');
  const nombre = document.getElementById('recurso-nombre').value;
  const url = document.getElementById('recurso-url').value.trim();
  if (!url) {
    mostrarErrorCampo('recurso-error', 'Indica un enlace.');
    return;
  }
  const boton = e.submitter || e.target.querySelector('button[type="submit"]');
  boton.classList.add('is-loading');
  try {
    await api(`/asignaturas/${asignaturaId}/recursos-externos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre, url }),
    });
    e.target.reset();
    await cargarCabeceraYResumen();
  } catch (err) {
    mostrarErrorCampo('recurso-error', err.message);
  } finally {
    boton.classList.remove('is-loading');
  }
});

// --- Notas rápidas (autosave) ---

(function () {
  const textarea = document.getElementById('notas-rapidas');
  const estado = document.getElementById('notas-guardado-estado');
  if (!textarea) return;

  let timer = null;
  textarea.addEventListener('input', () => {
    estado.textContent = '';
    estado.classList.remove('es-error');
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        await api(`/asignaturas/${asignaturaId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ notas: textarea.value }),
        });
        estado.textContent = 'Guardado ✓';
        setTimeout(() => { estado.textContent = ''; }, 2000);
      } catch (err) {
        estado.textContent = 'Error al guardar: ' + err.message;
        estado.classList.add('es-error');
      }
    }, 600);
  });
})();

// --- Tareas ---

function calcularCountdown(fechaIso) {
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const fecha = new Date(fechaIso + 'T00:00:00');
  const dias = Math.round((fecha - hoy) / 86400000);
  if (dias < 0) return `Atrasada ${-dias} día${-dias !== 1 ? 's' : ''}`;
  if (dias === 0) return 'Hoy';
  return `Faltan ${dias} día${dias !== 1 ? 's' : ''}`;
}

const ETIQUETA_TIPO_TAREA = { examen: 'Examen', entrega: 'Entrega', tarea_general: 'Tarea', tutoria: 'Tutoría' };

async function cargarTareas() {
  const tareas = await api(`/tareas?asignatura_id=${asignaturaId}`);
  const contenedor = document.getElementById('tareas-lista');

  if (tareas.length === 0) {
    contenedor.innerHTML = '<p class="sin-elementos">Sin tareas todavía.</p>';
    return;
  }

  const ordenadas = [...tareas].sort((a, b) => a.fecha.localeCompare(b.fecha));

  contenedor.innerHTML = ordenadas.map((t) => `
    <div class="detalle-fila" data-id="${t.id}">
      <input type="checkbox" class="tarea-fila-check" ${t.completada ? 'checked' : ''}>
      <div class="tarea-fila-titulo ${t.completada ? 'completada' : ''}">
        <span class="ds-body">${escapeHtml(t.titulo)}</span>
        <p class="ds-caption">${t.fecha}${t.completada ? '' : ' · ' + calcularCountdown(t.fecha)}</p>
      </div>
      <div class="tarea-fila-badges">
        <span class="ds-badge">${ETIQUETA_TIPO_TAREA[t.tipo] || 'Tarea'}</span>
      </div>
      <div class="fila-acciones">
        <button type="button" class="fila-icono-btn btn-borrar-tarea" title="Eliminar">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
        </button>
      </div>
    </div>
  `).join('');
  reanimar(contenedor);

  contenedor.querySelectorAll('.detalle-fila').forEach((fila) => {
    const id = fila.dataset.id;
    fila.querySelector('.tarea-fila-check').addEventListener('change', async (e) => {
      await api(`/tareas/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completada: e.target.checked }),
      });
      await cargarTareas();
    });
    fila.querySelector('.btn-borrar-tarea').addEventListener('click', async () => {
      if (!confirm('¿Eliminar esta tarea? Esta acción no se puede deshacer.')) return;
      await api(`/tareas/${id}`, { method: 'DELETE' });
      await cargarTareas();
      mostrarToast('Tarea eliminada', 'success');
    });
  });
}

document.getElementById('form-nueva-tarea').addEventListener('submit', async (e) => {
  e.preventDefault();
  mostrarErrorCampo('tarea-error', '');
  const titulo = document.getElementById('tarea-titulo').value.trim();
  const fecha = document.getElementById('tarea-fecha').value;
  const tipo = document.getElementById('tarea-tipo').value;
  if (!titulo || !fecha) {
    mostrarErrorCampo('tarea-error', 'Indica un título y una fecha.');
    return;
  }
  const boton = e.submitter || e.target.querySelector('button[type="submit"]');
  boton.classList.add('is-loading');
  try {
    await api('/tareas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ titulo, fecha, tipo, asignatura_id: asignaturaId }),
    });
    e.target.reset();
    await cargarTareas();
  } catch (err) {
    mostrarErrorCampo('tarea-error', err.message);
  } finally {
    boton.classList.remove('is-loading');
  }
});

// --- Documentos: categorías fijas + subgrupos libres ---

const CATEGORIAS_DOCUMENTO_LISTA = [
  { categoria: 'teoria', etiqueta: 'Teoría' },
  { categoria: 'examenes', etiqueta: 'Exámenes' },
  { categoria: 'laboratorios', etiqueta: 'Laboratorios' },
  { categoria: 'otros', etiqueta: 'Otros' },
];

let vistaDocumentos = localStorage.getItem('documentos-vista') || 'lista';
let categoriaActual = null; // null = raíz (las 4 categorías)
let grupoActual = null;     // {id, nombre} o null
let ARBOL_DOCUMENTOS = [];
let GRUPOS_CATEGORIA_ACTUAL = [];
let DOCUMENTOS_SIN_CLASIFICAR = [];
let DOCUMENTOS_GRUPO_ACTUAL = [];
let asignaturaCorta = '';

document.querySelectorAll('#documentos-vista-toggle .filtro-chip').forEach((b) => {
  b.classList.toggle('is-active', b.dataset.vista === vistaDocumentos);
});

function formatoTamano(bytes) {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function cargarDocumentosRaiz() {
  ARBOL_DOCUMENTOS = await api(`/asignaturas/${asignaturaId}/documentos/arbol`);
  renderDocumentos();
}

async function cargarDocumentosCategoria() {
  const [grupos, sinClasificar] = await Promise.all([
    api(`/asignaturas/${asignaturaId}/grupos?categoria=${categoriaActual}`),
    api(`/asignaturas/${asignaturaId}/categorias/${categoriaActual}/documentos`),
  ]);
  GRUPOS_CATEGORIA_ACTUAL = grupos;
  DOCUMENTOS_SIN_CLASIFICAR = sinClasificar;
  renderDocumentos();
}

async function cargarDocumentosGrupo() {
  DOCUMENTOS_GRUPO_ACTUAL = await api(
    `/asignaturas/${asignaturaId}/categorias/${categoriaActual}/documentos?grupo_id=${grupoActual.id}`
  );
  renderDocumentos();
}

async function recargarVistaActual() {
  if (categoriaActual === null) await cargarDocumentosRaiz();
  else if (grupoActual === null) await cargarDocumentosCategoria();
  else await cargarDocumentosGrupo();
}

function renderDocumentos() {
  renderBreadcrumbsDocumentos();
  actualizarToolbarDocumentos();
  if (categoriaActual === null) renderCategorias();
  else if (grupoActual === null) renderCategoriaAbierta();
  else renderGrupoAbierto();
  actualizarFiltroEtiquetas();
}

// --- Breadcrumbs: "SIGLAS > Documentos > Categoría > Subgrupo" ---

function renderBreadcrumbsDocumentos() {
  const nav = document.getElementById('documentos-breadcrumbs');
  const partes = [];
  if (asignaturaCorta) partes.push(`<span class="documentos-breadcrumb-item documentos-breadcrumb-item--fijo">${escapeHtml(asignaturaCorta)}</span>`);
  partes.push(`<span class="documentos-breadcrumb-sep">›</span>`);
  partes.push(`<button type="button" class="documentos-breadcrumb-item" data-nivel="raiz">Documentos</button>`);

  if (categoriaActual) {
    const etiqueta = CATEGORIAS_DOCUMENTO_LISTA.find((c) => c.categoria === categoriaActual).etiqueta;
    partes.push(`<span class="documentos-breadcrumb-sep">›</span>`);
    partes.push(`<button type="button" class="documentos-breadcrumb-item${grupoActual ? '' : ' is-actual'}" data-nivel="categoria">${escapeHtml(etiqueta)}</button>`);
  }
  if (grupoActual) {
    partes.push(`<span class="documentos-breadcrumb-sep">›</span>`);
    partes.push(`<span class="documentos-breadcrumb-item is-actual">${escapeHtml(grupoActual.nombre)}</span>`);
  }
  nav.innerHTML = partes.join('');

  const raiz = nav.querySelector('[data-nivel="raiz"]');
  if (raiz) raiz.addEventListener('click', () => { categoriaActual = null; grupoActual = null; cargarDocumentosRaiz(); });
  const cat = nav.querySelector('[data-nivel="categoria"]');
  if (cat) cat.addEventListener('click', () => { grupoActual = null; cargarDocumentosCategoria(); });
}

function actualizarToolbarDocumentos() {
  const enRaiz = categoriaActual === null;
  document.getElementById('form-nuevo-grupo').style.display = (categoriaActual && !grupoActual) ? '' : 'none';
  document.getElementById('documentos-btn-subir').style.display = enRaiz ? 'none' : '';
  document.getElementById('filtro-etiqueta').closest('.ds-field').style.display = enRaiz ? 'none' : '';
}

// --- Nivel raíz: las 4 categorías fijas ---

function renderCategorias() {
  const cont = document.getElementById('documentos-explorador');
  cont.className = `documentos-explorador documentos-explorador--${vistaDocumentos}`;
  cont.innerHTML = `<div class="documentos-carpetas-grid">${ARBOL_DOCUMENTOS.map((cat) => `
    <button type="button" class="documento-carpeta" data-categoria="${cat.categoria}">
      <svg class="ds-icon documento-carpeta-icono"><use href="/static/vendor/lucide/sprite.svg#lucide-folder"></use></svg>
      <span class="documento-carpeta-nombre">${escapeHtml(cat.etiqueta)}</span>
      <span class="ds-caption">${cat.total_documentos} documento${cat.total_documentos !== 1 ? 's' : ''}</span>
    </button>
  `).join('')}</div>`;
  reanimar(cont);

  cont.querySelectorAll('.documento-carpeta').forEach((btn) => {
    const categoria = btn.dataset.categoria;
    btn.addEventListener('click', () => { categoriaActual = categoria; grupoActual = null; cargarDocumentosCategoria(); });
    registrarDropzone(btn, { categoria, grupoId: null });
  });
}

// --- Nivel categoría: subgrupos (carpetas) + documentos sin clasificar ---

function renderCategoriaAbierta() {
  const cont = document.getElementById('documentos-explorador');
  cont.className = `documentos-explorador documentos-explorador--${vistaDocumentos}`;

  const carpetas = GRUPOS_CATEGORIA_ACTUAL.map((g) => `
    <div class="documento-carpeta" data-grupo-id="${g.id}" data-grupo-nombre="${escapeHtml(g.nombre)}" tabindex="0" role="button">
      <svg class="ds-icon documento-carpeta-icono"><use href="/static/vendor/lucide/sprite.svg#lucide-folder"></use></svg>
      <span class="documento-carpeta-nombre">${escapeHtml(g.nombre)}</span>
      <span class="ds-caption">${g.total_documentos} documento${g.total_documentos !== 1 ? 's' : ''}</span>
      <div class="documento-carpeta-acciones">
        <button type="button" class="fila-icono-btn btn-renombrar-grupo" data-id="${g.id}" title="Renombrar">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-tag"></use></svg>
        </button>
        <button type="button" class="fila-icono-btn btn-borrar-grupo" data-id="${g.id}" data-nombre="${escapeHtml(g.nombre)}" title="Eliminar subgrupo">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
        </button>
      </div>
    </div>
  `).join('');

  cont.innerHTML = `
    ${carpetas ? `<div class="documentos-carpetas-grid">${carpetas}</div>` : ''}
    <h3 class="ds-h3 documentos-sin-clasificar-titulo" id="documentos-sin-clasificar-zona">Sin clasificar</h3>
    <div class="documentos-lista-archivos" id="documentos-lista-sin-clasificar"></div>
  `;

  renderListaDocumentos(document.getElementById('documentos-lista-sin-clasificar'), DOCUMENTOS_SIN_CLASIFICAR);
  reanimar(cont);

  cont.querySelectorAll('.documento-carpeta[data-grupo-id]').forEach((tarjeta) => {
    const grupoId = parseInt(tarjeta.dataset.grupoId, 10);
    tarjeta.addEventListener('click', (e) => {
      if (e.target.closest('.documento-carpeta-acciones')) return;
      grupoActual = { id: grupoId, nombre: tarjeta.dataset.grupoNombre };
      cargarDocumentosGrupo();
    });
    registrarDropzone(tarjeta, { categoria: categoriaActual, grupoId });
  });
  cont.querySelectorAll('.btn-renombrar-grupo').forEach((btn) => {
    btn.addEventListener('click', (e) => { e.stopPropagation(); renombrarGrupo(parseInt(btn.dataset.id, 10)); });
  });
  cont.querySelectorAll('.btn-borrar-grupo').forEach((btn) => {
    btn.addEventListener('click', (e) => { e.stopPropagation(); confirmarBorrarGrupo(parseInt(btn.dataset.id, 10), btn.dataset.nombre); });
  });

  registrarDropzone(document.getElementById('documentos-sin-clasificar-zona'), { categoria: categoriaActual, grupoId: null });
  registrarDropzoneFondo(cont, { categoria: categoriaActual, grupoId: null });
}

// --- Nivel subgrupo: solo sus documentos ---

function renderGrupoAbierto() {
  const cont = document.getElementById('documentos-explorador');
  cont.className = `documentos-explorador documentos-explorador--${vistaDocumentos}`;
  cont.innerHTML = `<div class="documentos-lista-archivos" id="documentos-lista-grupo"></div>`;
  renderListaDocumentos(document.getElementById('documentos-lista-grupo'), DOCUMENTOS_GRUPO_ACTUAL);
  reanimar(cont);
  registrarDropzoneFondo(cont, { categoria: categoriaActual, grupoId: grupoActual.id });
}

// --- Lista/cuadrícula de documentos (reutilizada en "sin clasificar" y dentro de un subgrupo) ---

function renderListaDocumentos(contenedor, documentos) {
  if (!contenedor) return;
  if (documentos.length === 0) {
    contenedor.innerHTML = '<p class="sin-elementos">Sin documentos aquí todavía. Arrastra archivos o usa "Subir archivos".</p>';
    return;
  }
  contenedor.innerHTML = documentos.map((doc) => {
    const urlArchivo = `/documentos/${doc.id}/archivo`;
    const miniatura = doc.es_imagen
      ? `<img src="${urlArchivo}" class="miniatura-documento" alt="${escapeHtml(doc.nombre_archivo)}">`
      : '<div class="documento-fila-icono"><svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-folder"></use></svg></div>';
    const etiquetasHtml = doc.etiquetas.map((e) => `<span class="tag-badge">${escapeHtml(e)}</span>`).join('');
    const progresoLectura = (doc.es_pdf && doc.porcentaje_leido)
      ? `<div class="ds-progress documento-fila-progreso"><div class="ds-progress-bar" style="width:${Math.round(doc.porcentaje_leido * 100)}%"></div></div>`
      : '';
    return `
      <div class="documento-fila" draggable="true" data-id="${doc.id}" data-etiquetas="${doc.etiquetas.join(',').toLowerCase()}">
        ${miniatura}
        <span class="documento-fila-nombre-col">
          <a href="#" class="documento-fila-nombre abrir-documento">${escapeHtml(doc.nombre_archivo)}</a>
          ${progresoLectura}
        </span>
        <span class="tags-documento">${etiquetasHtml}</span>
        <span class="documento-fila-meta">${formatoTamano(doc.tamano_bytes)}</span>
        <span class="documento-fila-fecha">${new Date(doc.fecha_subida).toLocaleDateString()}</span>
        <div class="documento-fila-acciones">
          ${(doc.es_pdf && categoriaActual === 'teoria') ? `
          <button type="button" class="fila-icono-btn btn-extraer-guia" data-tooltip="Extraer datos de guía docente" aria-label="Extraer datos de guía docente">
            <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-book-check"></use></svg>
          </button>` : ''}
          <button type="button" class="fila-icono-btn btn-editar-etiquetas" data-tooltip="Editar etiquetas" aria-label="Editar etiquetas">
            <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-tag"></use></svg>
          </button>
          <button type="button" class="fila-icono-btn btn-mover-doc" data-tooltip="Mover a..." aria-label="Mover a...">
            <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-folder"></use></svg>
          </button>
          <a class="fila-icono-btn descargar" href="${urlArchivo}" download data-tooltip="Descargar" aria-label="Descargar">
            <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-download"></use></svg>
          </a>
          <button type="button" class="fila-icono-btn btn-borrar-doc" data-tooltip="Eliminar" aria-label="Eliminar">
            <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
          </button>
        </div>
      </div>
    `;
  }).join('');

  contenedor.querySelectorAll('.documento-fila').forEach((fila) => {
    const id = parseInt(fila.dataset.id, 10);
    const doc = documentos.find((d) => d.id === id);
    const urlArchivo = `/documentos/${doc.id}/archivo`;

    fila.querySelector('.abrir-documento').addEventListener('click', (e) => {
      e.preventDefault();
      if (doc.es_pdf) abrirVisorPdf(doc.id);
      else if (doc.es_imagen) abrirLightbox(urlArchivo, doc.nombre_archivo);
      else window.open(urlArchivo, '_blank');
    });
    if (doc.es_imagen) {
      fila.querySelector('.miniatura-documento').addEventListener('click', () => abrirLightbox(urlArchivo, doc.nombre_archivo));
    }
    fila.querySelector('.btn-editar-etiquetas').addEventListener('click', () => editarEtiquetas(doc));
    fila.querySelector('.btn-mover-doc').addEventListener('click', (e) => abrirMenuMover(doc, e.currentTarget));
    fila.querySelector('.btn-borrar-doc').addEventListener('click', () => confirmarBorrarDocumento(doc));
    const btnExtraerGuia = fila.querySelector('.btn-extraer-guia');
    if (btnExtraerGuia) btnExtraerGuia.addEventListener('click', () => abrirModalGuiaDocente(doc.id));

    fila.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('application/x-documento-id', String(doc.id));
      e.dataTransfer.effectAllowed = 'move';
    });

    fila.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      abrirMenuContextual([
        { etiqueta: 'Abrir', accion: () => fila.querySelector('.abrir-documento').click() },
        { etiqueta: 'Descargar', accion: () => window.open(urlArchivo, '_blank') },
        { etiqueta: 'Mover a…', accion: () => abrirMenuMover(doc, fila.querySelector('.btn-mover-doc')) },
        { etiqueta: 'Editar etiquetas', accion: () => editarEtiquetas(doc) },
        { separador: true },
        { etiqueta: 'Eliminar', peligroso: true, accion: () => confirmarBorrarDocumento(doc) },
      ], { x: e.clientX, y: e.clientY, anclaEl: fila });
    });
  });
}

// --- Drag & drop: archivos del SO (subida) y documentos internos (mover) ---

function registrarDropzone(elemento, destino) {
  elemento.addEventListener('dragover', (e) => { e.preventDefault(); e.stopPropagation(); elemento.classList.add('dragover'); });
  elemento.addEventListener('dragleave', () => elemento.classList.remove('dragover'));
  elemento.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    elemento.classList.remove('dragover');
    await gestionarDrop(e, destino);
  });
}

// Fondo del explorador (fuera de cualquier tarjeta): mismo destino que "Sin clasificar".
// stopPropagation() en registrarDropzone() de las tarjetas evita que un drop sobre una
// tarjeta concreta "caiga también" en este listener de fondo.
function registrarDropzoneFondo(elemento, destino) {
  elemento.addEventListener('dragover', (e) => e.preventDefault());
  elemento.addEventListener('drop', async (e) => {
    e.preventDefault();
    await gestionarDrop(e, destino);
  });
}

async function gestionarDrop(e, destino) {
  const idInterno = e.dataTransfer.getData('application/x-documento-id');
  if (idInterno) {
    await moverDocumento(parseInt(idInterno, 10), destino.categoria, destino.grupoId);
    return;
  }
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    await subirArchivos(destino.categoria, destino.grupoId, e.dataTransfer.files);
  }
}

document.getElementById('input-subir-documentos').addEventListener('change', async (e) => {
  await subirArchivos(categoriaActual, grupoActual ? grupoActual.id : null, e.target.files);
  e.target.value = '';
});

// --- Subida con barra de progreso real (XHR: fetch no expone progreso de subida) ---

function subidaConProgreso(url, formData, alActualizar) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) xhr.setRequestHeader('X-CSRFToken', meta.content);
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) alActualizar(Math.round((e.loaded / e.total) * 100));
    });
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else {
        let mensaje = `Error ${xhr.status}`;
        try { mensaje = JSON.parse(xhr.responseText).error || mensaje; } catch (err) { /* respuesta sin JSON */ }
        reject(new Error(mensaje));
      }
    };
    xhr.onerror = () => reject(new Error('Error de red al subir el archivo'));
    xhr.send(formData);
  });
}

async function subirArchivos(categoria, grupoId, files) {
  if (!files || files.length === 0) return;
  mostrarErrorCampo('documentos-error', '');
  const formData = new FormData();
  for (const file of files) formData.append('archivos', file);
  if (grupoId) formData.append('grupo_id', grupoId);

  const cont = document.getElementById('documentos-progreso');
  const barra = document.getElementById('documentos-progreso-barra');
  const texto = document.getElementById('documentos-progreso-texto');
  cont.style.display = '';
  barra.style.width = '0%';
  texto.textContent = `Subiendo ${files.length} archivo${files.length !== 1 ? 's' : ''}...`;

  try {
    await subidaConProgreso(
      `/asignaturas/${asignaturaId}/categorias/${categoria}/documentos`,
      formData,
      (pct) => { barra.style.width = `${pct}%`; },
    );
    await recargarVistaActual();
    mostrarToast(`${files.length} archivo${files.length !== 1 ? 's' : ''} subido${files.length !== 1 ? 's' : ''}`, 'success');
  } catch (err) {
    mostrarErrorCampo('documentos-error', 'Error al subir: ' + err.message);
  } finally {
    setTimeout(() => { cont.style.display = 'none'; }, 400);
  }
}

// --- Mover documento (menú "Mover a...", drag&drop interno) ---

async function moverDocumento(documentoId, categoria, grupoId) {
  try {
    await api(`/documentos/${documentoId}/mover`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ categoria, grupo_id: grupoId }),
    });
    await recargarVistaActual();
    mostrarToast('Documento movido', 'success');
  } catch (err) {
    mostrarToast('Error al mover: ' + err.message, 'danger');
  }
}

function cerrarMenuMover() {
  const existente = document.getElementById('menu-mover-documento');
  if (existente) existente.remove();
  document.removeEventListener('click', cerrarMenuMoverSiFuera);
}

function cerrarMenuMoverSiFuera(e) {
  const menu = document.getElementById('menu-mover-documento');
  if (menu && !menu.contains(e.target)) cerrarMenuMover();
}

async function abrirMenuMover(doc, botonAncla) {
  cerrarMenuMover();
  const menu = document.createElement('div');
  menu.id = 'menu-mover-documento';
  menu.className = 'documentos-menu-mover';
  menu.innerHTML = `
    <p class="ds-label">Mover "${escapeHtml(doc.nombre_archivo)}" a…</p>
    <select class="ds-select" id="mover-categoria">
      ${CATEGORIAS_DOCUMENTO_LISTA.map((c) => `<option value="${c.categoria}" ${c.categoria === doc.categoria ? 'selected' : ''}>${escapeHtml(c.etiqueta)}</option>`).join('')}
    </select>
    <select class="ds-select" id="mover-grupo"><option value="">(Sin clasificar)</option></select>
    <div class="documentos-menu-mover-acciones">
      <button type="button" class="ds-btn ds-btn-secondary" id="mover-cancelar">Cancelar</button>
      <button type="button" class="ds-btn ds-btn-primary" id="mover-confirmar">Mover</button>
    </div>
  `;
  document.body.appendChild(menu);
  const rect = botonAncla.getBoundingClientRect();
  menu.style.top = `${window.scrollY + rect.bottom + 4}px`;
  menu.style.left = `${Math.min(window.scrollX + rect.left, window.scrollX + document.documentElement.clientWidth - 260)}px`;

  async function poblarGrupos(categoriaSeleccionada) {
    const grupos = await api(`/asignaturas/${asignaturaId}/grupos?categoria=${categoriaSeleccionada}`);
    const select = document.getElementById('mover-grupo');
    if (!select) return;
    select.innerHTML = '<option value="">(Sin clasificar)</option>' + grupos.map((g) =>
      `<option value="${g.id}" ${categoriaSeleccionada === doc.categoria && g.id === doc.grupo_documento_id ? 'selected' : ''}>${escapeHtml(g.nombre)}</option>`
    ).join('');
  }
  await poblarGrupos(doc.categoria);

  document.getElementById('mover-categoria').addEventListener('change', (e) => poblarGrupos(e.target.value));
  document.getElementById('mover-cancelar').addEventListener('click', cerrarMenuMover);
  document.getElementById('mover-confirmar').addEventListener('click', async () => {
    const categoria = document.getElementById('mover-categoria').value;
    const grupoIdRaw = document.getElementById('mover-grupo').value;
    cerrarMenuMover();
    await moverDocumento(doc.id, categoria, grupoIdRaw ? parseInt(grupoIdRaw, 10) : null);
  });
  setTimeout(() => document.addEventListener('click', cerrarMenuMoverSiFuera), 0);
}

// --- Subgrupos: crear / renombrar / eliminar ---

document.getElementById('form-nuevo-grupo').addEventListener('submit', async (e) => {
  e.preventDefault();
  mostrarErrorCampo('documentos-error', '');
  const campo = document.getElementById('nuevo-grupo-nombre');
  const nombre = campo.value.trim();
  if (!nombre) {
    mostrarErrorCampo('documentos-error', 'Indica un nombre para el subgrupo.');
    return;
  }
  const boton = e.submitter || e.target.querySelector('button[type="submit"]');
  boton.classList.add('is-loading');
  try {
    await api(`/asignaturas/${asignaturaId}/grupos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ categoria: categoriaActual, nombre }),
    });
    campo.value = '';
    await cargarDocumentosCategoria();
    mostrarToast('Subgrupo creado', 'success');
  } catch (err) {
    mostrarErrorCampo('documentos-error', err.message);
  } finally {
    boton.classList.remove('is-loading');
  }
});

async function renombrarGrupo(grupoId) {
  const grupo = GRUPOS_CATEGORIA_ACTUAL.find((g) => g.id === grupoId);
  const nuevo = prompt('Nuevo nombre del subgrupo:', grupo ? grupo.nombre : '');
  if (nuevo === null) return;
  try {
    await api(`/grupos/${grupoId}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre: nuevo }),
    });
    await cargarDocumentosCategoria();
    mostrarToast('Subgrupo renombrado', 'success');
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

async function confirmarBorrarGrupo(grupoId, nombre) {
  if (!confirm(`¿Eliminar el subgrupo "${nombre}"? Sus documentos pasarán a "Sin clasificar" (no se borran).`)) return;
  await api(`/grupos/${grupoId}`, { method: 'DELETE' });
  await cargarDocumentosCategoria();
  mostrarToast('Subgrupo eliminado', 'success');
}

// --- Vista lista/cuadrícula (recuerda la última usada) ---

document.getElementById('documentos-vista-toggle').addEventListener('click', (e) => {
  const boton = e.target.closest('.filtro-chip');
  if (!boton) return;
  document.querySelectorAll('#documentos-vista-toggle .filtro-chip').forEach((b) => b.classList.remove('is-active'));
  boton.classList.add('is-active');
  vistaDocumentos = boton.dataset.vista;
  localStorage.setItem('documentos-vista', vistaDocumentos);
  renderDocumentos();
});

// --- Etiquetas y borrado de documentos ---

async function editarEtiquetas(doc) {
  const actuales = doc.etiquetas.join(', ');
  const respuesta = prompt('Etiquetas separadas por comas:', actuales);
  if (respuesta === null) return;
  const etiquetas = respuesta.split(',').map((e) => e.trim()).filter(Boolean);
  await api(`/documentos/${doc.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ etiquetas }),
  });
  await recargarVistaActual();
  mostrarToast('Etiquetas actualizadas', 'success');
}

function actualizarFiltroEtiquetas() {
  const select = document.getElementById('filtro-etiqueta');
  if (!select) return;
  const valorActual = select.value;

  const todas = new Set();
  document.querySelectorAll('.documento-fila').forEach((fila) => {
    (fila.dataset.etiquetas || '').split(',').forEach((e) => { if (e) todas.add(e); });
  });

  select.innerHTML = '<option value="">(todas)</option>' +
    Array.from(todas).sort().map((e) => `<option value="${escapeHtml(e)}">${escapeHtml(e)}</option>`).join('');

  if (todas.has(valorActual)) select.value = valorActual;
  aplicarFiltroEtiqueta();
}

function aplicarFiltroEtiqueta() {
  const select = document.getElementById('filtro-etiqueta');
  if (!select) return;
  const filtro = select.value.toLowerCase();
  document.querySelectorAll('.documento-fila').forEach((fila) => {
    const etiquetas = (fila.dataset.etiquetas || '').split(',');
    fila.style.display = (!filtro || etiquetas.includes(filtro)) ? '' : 'none';
  });
}

document.getElementById('filtro-etiqueta').addEventListener('change', aplicarFiltroEtiqueta);

function abrirLightbox(url, alt) {
  let lightbox = document.getElementById('lightbox');
  if (!lightbox) {
    lightbox = document.createElement('div');
    lightbox.id = 'lightbox';
    lightbox.className = 'lightbox oculto';
    lightbox.innerHTML = '<img id="lightbox-img" src="" alt="">';
    lightbox.addEventListener('click', () => lightbox.classList.add('oculto'));
    document.body.appendChild(lightbox);
  }
  document.getElementById('lightbox-img').src = url;
  document.getElementById('lightbox-img').alt = alt || '';
  lightbox.classList.remove('oculto');
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const lightbox = document.getElementById('lightbox');
    if (lightbox) lightbox.classList.add('oculto');
  }
});

async function confirmarBorrarDocumento(doc) {
  if (!confirm(`¿Borrar "${doc.nombre_archivo}"? Esta acción no se puede deshacer.`)) return;
  await api(`/documentos/${doc.id}`, { method: 'DELETE' });
  await recargarVistaActual();
  mostrarToast('Documento eliminado', 'success');
}

// --- Visor PDF (PDF.js embebido, varias pestañas) ---
// "Continúa donde lo dejaste": además de la página, se restaura/guarda zoom, modo de
// scroll/spread y tiempo de lectura acumulado (spec Continua_donde_lo_dejaste).
// "Varias pestañas" (spec V2.2_VISOR_PDF): cada documento abierto vive en su propio
// <iframe> (su propia instancia de PDF.js), mostrado/ocultado al cambiar de pestaña, de
// forma que cada uno conserva su página/zoom/scroll de forma independiente. Se limita
// el número de pestañas simultáneas porque cada una es una instancia completa de
// PDF.js (memoria/CPU no despreciables) — al superar el límite se cierra la menos
// usada recientemente, guardando antes su progreso.

const MAX_PESTANAS_PDF = 5;
const pestanasPdf = new Map(); // documentoId -> { iframe, tabBtn, nombreArchivo, sesionInicioMs, sesionEsNueva, debounceTimer, ultimoAcceso }

async function abrirVisorPdf(documentoId, paginaForzada) {
  const visor = document.getElementById('visor-pdf');
  const estabaOculto = visor.style.display !== 'block';
  visor.style.display = 'block';

  const existente = pestanasPdf.get(documentoId);
  if (existente) {
    if (paginaForzada) {
      try { existente.iframe.contentWindow.PDFViewerApplication.page = paginaForzada; } catch (err) { /* PDF.js de esa pestaña aún no listo, se ignora */ }
    }
    activarPestana(documentoId);
    if (estabaOculto) visor.scrollIntoView({ behavior: 'smooth' });
    return;
  }

  if (pestanasPdf.size >= MAX_PESTANAS_PDF) {
    const [idMasAntiguo] = [...pestanasPdf.entries()].sort((a, b) => a[1].ultimoAcceso - b[1].ultimoAcceso)[0];
    cerrarPestana(idMasAntiguo);
  }

  const doc = await api(`/documentos/${documentoId}`);
  const paginaInicial = paginaForzada || doc.ultima_pagina_vista || 1;

  const iframe = document.createElement('iframe');
  iframe.className = 'pdf-frame';
  document.getElementById('visor-iframes').appendChild(iframe);

  const tabBtn = document.createElement('button');
  tabBtn.type = 'button';
  tabBtn.className = 'visor-pestana';
  tabBtn.innerHTML = `
    <span class="visor-pestana-nombre">${escapeHtml(doc.nombre_archivo)}</span>
    <span class="visor-pestana-cerrar" title="Cerrar pestaña">
      <svg class="ds-icon ds-icon--sm"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
    </span>
  `;
  tabBtn.addEventListener('click', (e) => {
    if (e.target.closest('.visor-pestana-cerrar')) {
      e.stopPropagation();
      cerrarPestana(documentoId);
    } else {
      activarPestana(documentoId);
    }
  });
  document.getElementById('visor-pestanas').appendChild(tabBtn);

  pestanasPdf.set(documentoId, {
    iframe, tabBtn, nombreArchivo: doc.nombre_archivo,
    sesionInicioMs: Date.now(), sesionEsNueva: true,
    debounceTimer: null, ultimoAcceso: Date.now(),
  });

  const archivoUrl = encodeURIComponent(`/documentos/${documentoId}/archivo`);
  iframe.src = `/static/vendor/pdfjs/web/viewer.html?file=${archivoUrl}`;

  iframe.onload = () => {
    try {
      const app = iframe.contentWindow.PDFViewerApplication;
      if (!app) return;
      app.initializedPromise.then(() => {
        app.eventBus.on('pagesinit', () => {
          if (paginaInicial > 1) app.page = paginaInicial;
          if (doc.zoom_nivel) {
            try { app.pdfViewer.currentScaleValue = doc.zoom_nivel; } catch (err) { /* valor de zoom no válido, se ignora */ }
          }
          if (doc.modo_visualizacion) {
            const [scrollMode, spreadMode] = doc.modo_visualizacion.split(':').map(Number);
            try {
              if (!Number.isNaN(scrollMode)) app.pdfViewer.scrollMode = scrollMode;
              if (!Number.isNaN(spreadMode)) app.pdfViewer.spreadMode = spreadMode;
            } catch (err) { /* modo guardado no válido para este documento, se ignora */ }
          }
          if (doc.scroll_vertical) {
            setTimeout(() => { app.pdfViewer.container.scrollTop = doc.scroll_vertical; }, 100);
          }
        }, { once: true });
        app.eventBus.on('pagechanging', (evt) => guardarProgreso(documentoId, app, evt.pageNumber));
        app.eventBus.on('scalechanging', () => guardarProgreso(documentoId, app));
        app.eventBus.on('scrollmodechanged', () => guardarProgreso(documentoId, app));
        app.eventBus.on('spreadmodechanged', () => guardarProgreso(documentoId, app));
      });
    } catch (err) {
      console.warn('No se pudo enlazar con PDF.js:', err);
    }
  };

  activarPestana(documentoId);
  if (estabaOculto) visor.scrollIntoView({ behavior: 'smooth' });
}

function activarPestana(documentoId) {
  const entry = pestanasPdf.get(documentoId);
  if (!entry) return;
  documentoAbiertoId = documentoId;
  entry.ultimoAcceso = Date.now();
  document.getElementById('visor-titulo').textContent = entry.nombreArchivo;
  for (const [id, e] of pestanasPdf) {
    e.iframe.style.display = id === documentoId ? 'block' : 'none';
    e.tabBtn.classList.toggle('is-activa', id === documentoId);
  }
  cargarMarcadores(documentoId);
  cargarAnotaciones(documentoId);
}

const ETIQUETA_ANOTACION = {
  resaltado: 'Resaltado',
  subrayado: 'Subrayado',
  tachado: 'Tachado',
  nota: 'Nota',
};

async function cargarAnotaciones(documentoId) {
  const lista = document.getElementById('lista-anotaciones');
  if (!lista) return;
  const anotaciones = await api(`/documentos/${documentoId}/anotaciones`);
  lista.innerHTML = '';
  if (anotaciones.length === 0) {
    lista.innerHTML = '<li class="sin-elementos">Sin anotaciones todavía</li>';
    return;
  }
  for (const a of anotaciones) {
    const resumen = (a.texto || ETIQUETA_ANOTACION[a.tipo] || '').trim();
    const li = document.createElement('li');
    li.innerHTML = `
      <a href="#" class="ir-anotacion">
        <span class="anotacion-color"></span>
        <span class="anotacion-texto">Pág. ${a.numero_pagina} — ${escapeHtml(resumen)}</span>
      </a>
      <button type="button" class="fila-icono-btn btn-copiar-anotacion" title="Copiar el texto">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-copy"></use></svg>
      </button>
      <button type="button" class="fila-icono-btn btn-borrar-anotacion" title="Eliminar la anotación">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
      </button>
    `;
    li.querySelector('.anotacion-color').style.backgroundColor = a.color;
    li.querySelector('.ir-anotacion').addEventListener('click', (e) => {
      e.preventDefault();
      irAPagina(a.numero_pagina);
    });
    li.querySelector('.btn-copiar-anotacion').addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(a.texto || '');
        mostrarToast('Texto copiado', 'success');
      } catch (err) {
        mostrarToast('No se pudo copiar el texto', 'error');
      }
    });
    li.querySelector('.btn-borrar-anotacion').addEventListener('click', async () => {
      if (!confirm('¿Eliminar esta anotación? Esta acción no se puede deshacer.')) return;
      await api(`/anotaciones/${a.id}`, { method: 'DELETE' });
      await cargarAnotaciones(documentoId);
      recargarAnotacionesEnVisor(documentoId);
      mostrarToast('Anotación eliminada', 'success');
    });
    lista.appendChild(li);
  }
}

/** Tras borrar desde el panel hay que refrescar también el iframe, que mantiene
 *  su propia copia de las anotaciones ya pintadas. */
function recargarAnotacionesEnVisor(documentoId) {
  const entrada = pestanasPdf.get(documentoId);
  if (!entrada) return;
  try {
    entrada.iframe.contentWindow.greelecAnotaciones.recargar();
  } catch (err) { /* el iframe aún no está listo: se repintará al abrirlo */ }
}

// El visor (dentro del iframe) avisa cuando se crea, edita o borra una anotación.
window.addEventListener('message', (evento) => {
  if (evento.origin !== window.location.origin) return;
  const datos = evento.data || {};
  if (datos.tipo !== 'greelec:anotaciones-cambiadas') return;
  if (datos.documentoId === documentoAbiertoId) cargarAnotaciones(documentoAbiertoId);
});

function cerrarVisorPdf() {
  if (documentoAbiertoId) cerrarPestana(documentoAbiertoId);
}

function cerrarPestana(documentoId) {
  const entry = pestanasPdf.get(documentoId);
  if (!entry) return;
  try {
    const app = entry.iframe.contentWindow.PDFViewerApplication;
    if (app) flushProgreso(documentoId, app, entry);
  } catch (err) { /* iframe ya descargado o sin PDF.js inicializado, no hay nada que guardar */ }

  entry.iframe.onload = null;
  entry.iframe.remove();
  entry.tabBtn.remove();
  clearTimeout(entry.debounceTimer);
  pestanasPdf.delete(documentoId);

  if (documentoAbiertoId === documentoId) {
    documentoAbiertoId = null;
    const restante = [...pestanasPdf.entries()].sort((a, b) => b[1].ultimoAcceso - a[1].ultimoAcceso)[0];
    if (restante) {
      activarPestana(restante[0]);
    } else {
      document.getElementById('visor-pdf').style.display = 'none';
    }
  }
}

document.getElementById('btn-cerrar-visor').addEventListener('click', cerrarVisorPdf);

function _payloadProgreso(app, paginaForzada) {
  const pagina = paginaForzada || app.pdfViewer.currentPageNumber;
  const total = app.pdfViewer.pagesCount;
  return {
    pagina,
    porcentaje: total ? Math.round((pagina / total) * 100) / 100 : null,
    zoom: app.pdfViewer.currentScaleValue ? String(app.pdfViewer.currentScaleValue) : null,
    modo_visualizacion: `${app.pdfViewer.scrollMode}:${app.pdfViewer.spreadMode}`,
    scroll: app.pdfViewer.container ? app.pdfViewer.container.scrollTop : null,
  };
}

function guardarProgreso(documentoId, app, paginaForzada) {
  const entry = pestanasPdf.get(documentoId);
  if (!entry) return;
  clearTimeout(entry.debounceTimer);
  entry.debounceTimer = setTimeout(() => enviarProgreso(documentoId, _payloadProgreso(app, paginaForzada), entry), 800);
}

function flushProgreso(documentoId, app, entry) {
  entry = entry || pestanasPdf.get(documentoId);
  if (entry) clearTimeout(entry.debounceTimer);
  enviarProgreso(documentoId, _payloadProgreso(app), entry);
}

function enviarProgreso(documentoId, datos, entry) {
  entry = entry || pestanasPdf.get(documentoId);
  if (entry) {
    if (entry.sesionInicioMs) {
      datos.tiempo_sesion_segundos = Math.round((Date.now() - entry.sesionInicioMs) / 1000);
      entry.sesionInicioMs = Date.now();
    }
    if (entry.sesionEsNueva) {
      datos.nueva_sesion = true;
      entry.sesionEsNueva = false;
    }
  }
  const meta = document.querySelector('meta[name="csrf-token"]');
  fetch(`/documentos/${documentoId}/progreso`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': meta ? meta.content : '' },
    body: JSON.stringify(datos),
    keepalive: true,
  });
}

async function cargarMarcadores(documentoId) {
  const marcadores = await api(`/documentos/${documentoId}/marcadores`);
  const lista = document.getElementById('lista-marcadores');
  lista.innerHTML = '';
  if (marcadores.length === 0) {
    lista.innerHTML = '<li class="sin-elementos">Sin marcadores todavía</li>';
    return;
  }
  for (const m of marcadores) {
    const li = document.createElement('li');
    const etiqueta = `Pág. ${m.numero_pagina}${m.titulo ? ' — ' + escapeHtml(m.titulo) : ''}`;
    li.innerHTML = `
      <a href="#" class="ir-marcador">${etiqueta}</a>
      <button type="button" class="fila-icono-btn btn-borrar-marcador">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
      </button>
    `;
    li.querySelector('.ir-marcador').addEventListener('click', (e) => {
      e.preventDefault();
      irAPagina(m.numero_pagina);
    });
    li.querySelector('.btn-borrar-marcador').addEventListener('click', async () => {
      if (!confirm(`¿Borrar el marcador de la página ${m.numero_pagina}? Esta acción no se puede deshacer.`)) return;
      await api(`/marcadores/${m.id}`, { method: 'DELETE' });
      await cargarMarcadores(documentoId);
      mostrarToast('Marcador eliminado', 'success');
    });
    lista.appendChild(li);
  }
}

/** iframe de la pestaña activa del visor. Antes se buscaba por id 'pdf-frame',
 *  que dejó de existir al pasar el visor a varias pestañas. */
function iframeActivo() {
  const entrada = pestanasPdf.get(documentoAbiertoId);
  return entrada ? entrada.iframe : null;
}

function irAPagina(pagina) {
  const iframe = iframeActivo();
  if (!iframe) return;
  try {
    iframe.contentWindow.PDFViewerApplication.page = pagina;
  } catch (err) {
    const base = iframe.src.split('#')[0];
    iframe.src = `${base}#page=${pagina}`;
  }
}

document.getElementById('btn-anadir-marcador').addEventListener('click', async () => {
  if (!documentoAbiertoId) {
    alert('Abre primero un documento PDF para poder añadir un marcador.');
    return;
  }
  let paginaActual = 1;
  try {
    paginaActual = iframeActivo().contentWindow.PDFViewerApplication.page;
  } catch (err) { /* si no se puede leer, se usa la página 1 por defecto */ }

  const titulo = prompt('Nota para este marcador (opcional):', '') || null;
  await api(`/documentos/${documentoAbiertoId}/marcadores`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ numero_pagina: paginaActual, titulo }),
  });
  await cargarMarcadores(documentoAbiertoId);
});

// Deep-link desde el buscador global: /vista/asignaturas/<id>?doc=<id>&pagina=<n>
async function abrirDesdeUrlSiCorresponde() {
  const params = new URLSearchParams(window.location.search);
  const docId = params.get('doc');
  if (!docId) return;
  const pagina = params.get('pagina');
  await abrirVisorPdf(parseInt(docId, 10), pagina ? parseInt(pagina, 10) : null);
}

// --- Extracción de guía docente (análisis local del PDF, con confirmación obligatoria) ---

let gdEstadoActual = null; // { profesores, esquemas, tieneProfesores, tieneEsquemas, modoProfesores, modoEsquemas }

async function abrirModalGuiaDocente(documentoId) {
  const overlay = document.getElementById('modal-guia-docente');
  const body = document.getElementById('gd-modal-body');
  document.getElementById('gd-estado').textContent = '';
  overlay.classList.remove('oculto');
  body.innerHTML = '<p class="ds-caption">Analizando el PDF…</p>';

  try {
    const resultado = await api(`/documentos/${documentoId}/analizar-guia-docente`, { method: 'POST' });
    gdEstadoActual = {
      profesores: resultado.profesores.map((p) => ({ nombre: p.nombre, rol: p.rol || '' })),
      esquemas: resultado.esquemas.map((e) => ({
        nombre: e.nombre,
        componentes: e.componentes.map((c) => ({ ...c })),
        bloques: (e.bloques || []).map((b) => ({ ...b, componentes: b.componentes.map((c) => ({ ...c })) })),
        textoSinAnalizar: e.texto_sin_analizar,
      })),
      tieneProfesores: resultado.asignatura_tiene_profesores,
      tieneEsquemas: resultado.asignatura_tiene_esquemas,
      modoProfesores: 'añadir',
      modoEsquemas: 'añadir',
    };
    renderModalGuiaDocente();
  } catch (err) {
    body.innerHTML = `<p class="ds-field-error">No se ha podido analizar el PDF: ${escapeHtml(err.message)}</p>`;
  }
}

function cerrarModalGuiaDocente() {
  document.getElementById('modal-guia-docente').classList.add('oculto');
  gdEstadoActual = null;
}

function filaProfesorGuiaDocente(p, i) {
  return `
    <div class="gd-fila" data-idx="${i}">
      <div class="ds-field">
        <label class="ds-label">Nombre</label>
        <input type="text" class="ds-input gd-prof-nombre" value="${escapeHtml(p.nombre)}">
      </div>
      <div class="ds-field">
        <label class="ds-label">Rol / grupos</label>
        <input type="text" class="ds-input gd-prof-rol" value="${escapeHtml(p.rol)}">
      </div>
      <button type="button" class="fila-icono-btn gd-quitar-profesor" title="Quitar">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
      </button>
    </div>
  `;
}

function filaComponenteGuiaDocente(c, iEsquema, iComp) {
  const opciones = Object.keys(ETIQUETA_TIPO_COMPONENTE).map((tipo) =>
    `<option value="${tipo}" ${c.tipo === tipo ? 'selected' : ''}>${ETIQUETA_TIPO_COMPONENTE[tipo]}</option>`
  ).join('');
  return `
    <div class="gd-fila${c.pendiente_revision ? ' is-pendiente' : ''}" data-i-esquema="${iEsquema}" data-i-comp="${iComp}">
      <div class="ds-field">
        <label class="ds-label">Nombre</label>
        <input type="text" class="ds-input gd-comp-nombre" value="${escapeHtml(c.nombre)}">
      </div>
      <div class="ds-field" style="flex-basis:140px">
        <label class="ds-label">Tipo</label>
        <select class="ds-select gd-comp-tipo">${opciones}</select>
      </div>
      <div class="ds-field" style="flex-basis:90px">
        <label class="ds-label">% peso</label>
        <input type="number" class="ds-input gd-comp-porcentaje" min="0" max="100" step="0.01" value="${c.porcentaje != null ? c.porcentaje : ''}">
      </div>
      ${c.pendiente_revision ? '<span class="gd-etiqueta-pendiente">A revisar</span>' : ''}
      <button type="button" class="fila-icono-btn gd-quitar-componente" title="Quitar">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
      </button>
    </div>
  `;
}

function bloqueEsquemaGuiaDocente(esquema, i) {
  const suma = esquema.componentes.reduce((s, c) => s + (Number(c.porcentaje) || 0), 0)
    + (esquema.bloques || []).reduce((s, b) => s + (Number(b.porcentaje) || 0), 0);
  return `
    <div class="gd-esquema-bloque" data-idx="${i}">
      <div class="gd-esquema-encabezado">
        <input type="text" class="ds-input gd-esquema-nombre" value="${escapeHtml(esquema.nombre)}">
        <span class="ds-caption">Suma: ${suma.toFixed(2)}%</span>
        <button type="button" class="fila-icono-btn gd-quitar-esquema" title="Quitar esquema">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-trash-2"></use></svg>
        </button>
      </div>
      ${esquema.componentes.map((c, iComp) => filaComponenteGuiaDocente(c, i, iComp)).join('')}
      ${(esquema.bloques || []).map((b, iBloque) => `
        <div class="gd-fila gd-bloque-detectado" data-i-bloque="${iBloque}">
          <div>
            <span class="ds-body">${escapeHtml(b.nombre)} <span class="ds-badge ds-badge-accent">Bloque</span> ${b.porcentaje}%</span>
            <p class="ds-caption">${b.componentes.map((c) => `${escapeHtml(c.nombre)} ${c.porcentaje}%`).join(' · ')}</p>
          </div>
          <span class="gd-etiqueta-pendiente">A revisar</span>
          <button type="button" class="fila-icono-btn gd-quitar-bloque" title="Quitar bloque">
            <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
          </button>
        </div>`).join('')}
      <button type="button" class="ds-btn ds-btn-secondary gd-anadir-componente" style="margin-top:var(--ds-space-3)">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-plus"></use></svg>
        Añadir componente
      </button>
      ${esquema.textoSinAnalizar ? `
        <p class="ds-caption" style="margin-top:var(--ds-space-3)">No se ha podido determinar el desglose con confianza. Texto de la guía para revisar a mano:</p>
        <div class="gd-texto-crudo">${escapeHtml(esquema.textoSinAnalizar)}</div>
      ` : ''}
    </div>
  `;
}

function renderModalGuiaDocente() {
  const body = document.getElementById('gd-modal-body');
  const gd = gdEstadoActual;

  body.innerHTML = `
    <div class="gd-seccion">
      <div class="gd-seccion-titulo">
        <h3 class="ds-h3">Profesorado detectado</h3>
        <button type="button" id="gd-anadir-profesor" class="ds-btn ds-btn-secondary">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-plus"></use></svg>
          Añadir profesor
        </button>
      </div>
      ${gd.profesores.length === 0 ? '<p class="sin-elementos">No se ha detectado ningún profesor en la guía (campo vacío o sin publicar todavía).</p>' : ''}
      ${gd.profesores.map((p, i) => filaProfesorGuiaDocente(p, i)).join('')}
      ${gd.tieneProfesores ? `
        <div class="ds-field" style="margin-top:var(--ds-space-4);max-width:280px">
          <label for="gd-modo-profesores" class="ds-label">Esta asignatura ya tiene profesorado</label>
          <select id="gd-modo-profesores" class="ds-select">
            <option value="añadir">Añadir a los ya existentes</option>
            <option value="reemplazar">Reemplazar los existentes</option>
          </select>
        </div>
      ` : ''}
    </div>

    <div class="gd-seccion">
      <div class="gd-seccion-titulo">
        <h3 class="ds-h3">Esquema(s) de evaluación detectado(s)</h3>
        <button type="button" id="gd-anadir-esquema" class="ds-btn ds-btn-secondary">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-plus"></use></svg>
          Añadir esquema
        </button>
      </div>
      ${gd.esquemas.map((e, i) => bloqueEsquemaGuiaDocente(e, i)).join('')}
      ${gd.tieneEsquemas ? `
        <div class="ds-field" style="margin-top:var(--ds-space-4);max-width:280px">
          <label for="gd-modo-esquemas" class="ds-label">Esta asignatura ya tiene esquema(s) de evaluación</label>
          <select id="gd-modo-esquemas" class="ds-select">
            <option value="añadir">Añadir a los ya existentes</option>
            <option value="reemplazar">Reemplazar los existentes</option>
          </select>
        </div>
      ` : ''}
    </div>
  `;
  reanimar(body);
  wirModalGuiaDocente();
}

function wirModalGuiaDocente() {
  const gd = gdEstadoActual;
  const body = document.getElementById('gd-modal-body');

  // Profesores
  document.getElementById('gd-anadir-profesor').addEventListener('click', () => {
    gd.profesores.push({ nombre: '', rol: '' });
    renderModalGuiaDocente();
  });
  body.querySelectorAll('.gd-seccion:first-child > .gd-fila').forEach((fila) => {
    const i = Number(fila.dataset.idx);
    fila.querySelector('.gd-prof-nombre').addEventListener('input', (e) => { gd.profesores[i].nombre = e.target.value; });
    fila.querySelector('.gd-prof-rol').addEventListener('input', (e) => { gd.profesores[i].rol = e.target.value; });
    fila.querySelector('.gd-quitar-profesor').addEventListener('click', () => {
      gd.profesores.splice(i, 1);
      renderModalGuiaDocente();
    });
  });
  const selectModoProf = document.getElementById('gd-modo-profesores');
  if (selectModoProf) selectModoProf.addEventListener('change', (e) => { gd.modoProfesores = e.target.value; });

  // Esquemas
  document.getElementById('gd-anadir-esquema').addEventListener('click', () => {
    gd.esquemas.push({ nombre: 'Evaluación', componentes: [], bloques: [], textoSinAnalizar: null });
    renderModalGuiaDocente();
  });
  body.querySelectorAll('.gd-esquema-bloque').forEach((bloque) => {
    const iEsquema = Number(bloque.dataset.idx);
    bloque.querySelector('.gd-esquema-nombre').addEventListener('input', (e) => { gd.esquemas[iEsquema].nombre = e.target.value; });
    bloque.querySelector('.gd-quitar-esquema').addEventListener('click', () => {
      gd.esquemas.splice(iEsquema, 1);
      renderModalGuiaDocente();
    });
    bloque.querySelectorAll('.gd-quitar-bloque').forEach((btn) => btn.addEventListener('click', () => {
      gd.esquemas[iEsquema].bloques.splice(Number(btn.closest('[data-i-bloque]').dataset.iBloque), 1);
      renderModalGuiaDocente();
    }));
    bloque.querySelector('.gd-anadir-componente').addEventListener('click', () => {
      gd.esquemas[iEsquema].componentes.push({ nombre: '', tipo: 'otro', porcentaje: null, pendiente_revision: true });
      renderModalGuiaDocente();
    });
    bloque.querySelectorAll('.gd-fila[data-i-comp]').forEach((fila) => {
      const iComp = Number(fila.dataset.iComp);
      const componente = gd.esquemas[iEsquema].componentes[iComp];
      fila.querySelector('.gd-comp-nombre').addEventListener('input', (e) => { componente.nombre = e.target.value; });
      fila.querySelector('.gd-comp-tipo').addEventListener('change', (e) => { componente.tipo = e.target.value; });
      fila.querySelector('.gd-comp-porcentaje').addEventListener('input', (e) => {
        componente.porcentaje = e.target.value === '' ? null : Number(e.target.value);
      });
      fila.querySelector('.gd-quitar-componente').addEventListener('click', () => {
        gd.esquemas[iEsquema].componentes.splice(iComp, 1);
        renderModalGuiaDocente();
      });
    });
  });
  const selectModoEsq = document.getElementById('gd-modo-esquemas');
  if (selectModoEsq) selectModoEsq.addEventListener('change', (e) => { gd.modoEsquemas = e.target.value; });
}

document.getElementById('btn-cerrar-modal-guia').addEventListener('click', cerrarModalGuiaDocente);
document.getElementById('btn-descartar-guia').addEventListener('click', cerrarModalGuiaDocente);

document.getElementById('btn-confirmar-guia').addEventListener('click', async () => {
  const gd = gdEstadoActual;
  if (!gd) return;
  const estadoEl = document.getElementById('gd-estado');
  estadoEl.textContent = '';

  const profesores = gd.profesores.filter((p) => p.nombre.trim());
  const esquemas = gd.esquemas
    .map((e) => ({
      nombre: e.nombre.trim() || 'Evaluación',
      componentes: e.componentes.filter((c) => c.nombre.trim() && c.porcentaje !== null && c.porcentaje !== ''),
      bloques: (e.bloques || []).map((b) => ({ nombre: b.nombre, porcentaje: b.porcentaje, componentes: b.componentes })),
    }))
    .filter((e) => e.componentes.length + e.bloques.length > 0);

  if (profesores.length === 0 && esquemas.length === 0) {
    estadoEl.textContent = 'No hay nada que importar (añade al menos un profesor o un componente con % de peso).';
    estadoEl.classList.add('es-error');
    return;
  }

  const boton = document.getElementById('btn-confirmar-guia');
  boton.classList.add('is-loading');
  try {
    await api(`/asignaturas/${asignaturaId}/importar-guia-docente`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profesores,
        esquemas,
        modo_profesores: gd.modoProfesores,
        modo_esquemas: gd.modoEsquemas,
      }),
    });
    cerrarModalGuiaDocente();
    await cargarCabeceraYResumen();
    mostrarToast('Datos de la guía docente importados', 'success');
  } catch (err) {
    estadoEl.textContent = err.message;
    estadoEl.classList.add('es-error');
  } finally {
    boton.classList.remove('is-loading');
  }
});

// --- Inicio ---

mostrarEsqueletos();
cargarCabeceraYResumen();
cargarTareas();
cargarDocumentosRaiz().then(abrirDesdeUrlSiCorresponde);
