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

const SECCIONES = ['examenes_anteriores', 'teoria', 'ejercicios'];
const ETIQUETA_SECCION = { examenes_anteriores: 'Exámenes de años anteriores', teoria: 'Teoría', ejercicios: 'Ejercicios' };

let ESPACIO = null;
let seccionParaAnadir = null;

function formatoTamano(bytes) {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function urlAbrirDocumento(ref) {
  const asigId = ref.documento?.asignatura_id;
  return asigId ? `/vista/asignaturas/${asigId}?doc=${ref.documento_id}` : '#';
}

function filaDocumento(ref) {
  const doc = ref.documento || {};
  const fila = document.createElement('div');
  fila.className = `espacio-doc-fila${ref.leido ? ' es-leido' : ''}`;
  fila.draggable = true;
  fila.dataset.refId = ref.id;
  fila.dataset.seccion = ref.seccion;
  fila.innerHTML = `
    <input type="checkbox" class="ds-checkbox-nativo" ${ref.leido ? 'checked' : ''} data-tooltip="Marcar leído/pendiente" aria-label="Leído">
    <div class="espacio-doc-fila-info">
      <a href="${urlAbrirDocumento(ref)}" class="espacio-doc-fila-nombre">${escapeHtml(doc.nombre_archivo || '')}</a>
      <span class="ds-caption espacio-doc-fila-meta">${ref.documento_asignatura_siglas ? escapeHtml(ref.documento_asignatura_siglas) + ' · ' : ''}${formatoTamano(doc.tamano_bytes)}</span>
    </div>
    <div class="espacio-doc-fila-acciones">
      <button type="button" class="espacio-fila-icono-btn btn-destacar${ref.destacado ? ' es-destacado' : ''}" data-tooltip="${ref.destacado ? 'Quitar destacado' : 'Destacar'}" aria-label="Destacar">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-star"></use></svg>
      </button>
      <button type="button" class="espacio-fila-icono-btn btn-quitar-ref" data-tooltip="Quitar del espacio" aria-label="Quitar del espacio">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
      </button>
    </div>
  `;

  fila.querySelector('.ds-checkbox-nativo').addEventListener('change', (e) => {
    actualizarReferencia(ref.id, { leido: e.target.checked });
  });
  fila.querySelector('.btn-destacar').addEventListener('click', () => {
    actualizarReferencia(ref.id, { destacado: !ref.destacado });
  });
  fila.querySelector('.btn-quitar-ref').addEventListener('click', () => quitarReferencia(ref));

  fila.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('application/x-espacio-ref-id', String(ref.id));
    e.dataTransfer.effectAllowed = 'move';
  });

  fila.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    abrirMenuContextual([
      { etiqueta: 'Abrir', accion: () => window.open(urlAbrirDocumento(ref), '_blank') },
      { etiqueta: ref.leido ? 'Marcar como pendiente' : 'Marcar como leído', accion: () => actualizarReferencia(ref.id, { leido: !ref.leido }) },
      { etiqueta: ref.destacado ? 'Quitar destacado' : 'Destacar', accion: () => actualizarReferencia(ref.id, { destacado: !ref.destacado }) },
      { separador: true },
      { etiqueta: 'Quitar del espacio', peligroso: true, accion: () => quitarReferencia(ref) },
    ], { x: e.clientX, y: e.clientY, anclaEl: fila });
  });

  return fila;
}

function renderSeccion(seccion) {
  const contenedor = document.getElementById(`lista-${seccion}`);
  contenedor.innerHTML = '';
  const refs = ESPACIO.documentos_ref.filter((r) => r.seccion === seccion);
  if (refs.length === 0) {
    contenedor.innerHTML = `<p class="ds-caption sin-elementos">Sin documentos en ${ETIQUETA_SECCION[seccion].toLowerCase()} todavía.</p>`;
  } else {
    refs.forEach((ref) => contenedor.appendChild(filaDocumento(ref)));
  }
  registrarDropzone(contenedor, seccion);
}

function renderDestacados() {
  const contenedor = document.getElementById('lista-destacados');
  const refs = ESPACIO.documentos_ref.filter((r) => r.destacado);
  contenedor.innerHTML = '';
  if (refs.length === 0) {
    contenedor.innerHTML = '<p class="ds-caption sin-elementos">Marca documentos con ⭐ desde cualquier sección para verlos aquí.</p>';
  } else {
    refs.forEach((ref) => contenedor.appendChild(filaDocumento(ref)));
  }
}

function renderObjetivos() {
  const contenedor = document.getElementById('lista-objetivos');
  contenedor.innerHTML = '';
  if (ESPACIO.objetivos.length === 0) {
    contenedor.innerHTML = '<p class="ds-caption sin-elementos">Sin objetivos todavía.</p>';
    return;
  }
  ESPACIO.objetivos.forEach((obj) => {
    const fila = document.createElement('div');
    fila.className = `espacio-objetivo-fila${obj.completada ? ' es-completada' : ''}`;
    fila.innerHTML = `
      <input type="checkbox" class="ds-checkbox-nativo" ${obj.completada ? 'checked' : ''}>
      <span class="ds-body espacio-objetivo-texto">${escapeHtml(obj.texto)}</span>
      <button type="button" class="espacio-fila-icono-btn btn-borrar-objetivo" data-tooltip="Eliminar" aria-label="Eliminar">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
      </button>
    `;
    fila.querySelector('input').addEventListener('change', async (e) => {
      const objetivo = await api(`/espacios-estudio/objetivos/${obj.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completada: e.target.checked }),
      });
      obj.completada = objetivo.completada;
      fila.classList.toggle('es-completada', obj.completada);
    });
    fila.querySelector('.btn-borrar-objetivo').addEventListener('click', async () => {
      await api(`/espacios-estudio/objetivos/${obj.id}`, { method: 'DELETE' });
      await recargarEspacio();
      mostrarToast('Objetivo eliminado', 'success');
    });
    contenedor.appendChild(fila);
  });
}

function renderCabecera() {
  document.getElementById('titulo-pagina').textContent = `${ESPACIO.nombre} · GREELEC`;
  document.getElementById('espacio-nombre').textContent = ESPACIO.nombre;
  document.getElementById('espacio-asignatura').textContent = ESPACIO.asignatura_nombre
    ? `${ESPACIO.asignatura_nombre}${ESPACIO.profesores.length ? ' · ' + ESPACIO.profesores.join(', ') : ''}`
    : 'Sin asignatura';

  const fecha = new Date(ESPACIO.fecha + 'T00:00:00');
  document.getElementById('espacio-fecha').textContent = fecha.toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' });

  const dias = ESPACIO.dias_restantes;
  const cuentaAtras = document.getElementById('espacio-cuenta-atras');
  const urgente = dias !== null && dias <= 3 && dias >= 0;
  cuentaAtras.classList.toggle('es-urgente', urgente);
  cuentaAtras.querySelector('.espacio-cuenta-atras-icono').textContent = urgente ? '⚠' : '📅';
  document.getElementById('espacio-dias-restantes').textContent =
    dias < 0 ? `Hace ${-dias} día${-dias !== 1 ? 's' : ''}` : dias === 0 ? 'Es hoy' : `Faltan ${dias} día${dias !== 1 ? 's' : ''}`;

  document.getElementById('espacio-total-docs').textContent = ESPACIO.total_documentos;
  document.getElementById('espacio-docs-leidos').textContent = ESPACIO.documentos_leidos;
  document.getElementById('espacio-docs-pendientes').textContent = ESPACIO.documentos_pendientes;
  document.getElementById('espacio-progreso-pct').textContent = `${ESPACIO.progreso_pct}%`;
  document.getElementById('espacio-progreso-barra').style.width = `${ESPACIO.progreso_pct}%`;

  const btnCalendario = document.getElementById('espacio-btn-calendario');
  btnCalendario.href = `/vista/calendario?anio=${fecha.getFullYear()}&mes=${fecha.getMonth() + 1}`;
}

function renderEspacio() {
  renderCabecera();
  renderDestacados();
  SECCIONES.forEach(renderSeccion);
  renderObjetivos();
}

async function recargarEspacio() {
  ESPACIO = await api(`/espacios-estudio/${ESPACIO_ID}`);
  renderEspacio();
}

async function actualizarReferencia(refId, cambios) {
  try {
    await api(`/espacios-estudio/documentos/${refId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cambios),
    });
    await recargarEspacio();
  } catch (err) {
    mostrarToast('Error: ' + err.message, 'danger');
  }
}

async function quitarReferencia(ref) {
  if (!confirm(`¿Quitar "${ref.documento?.nombre_archivo}" de este espacio? El documento no se elimina, solo deja de estar referenciado aquí.`)) return;
  try {
    await api(`/espacios-estudio/documentos/${ref.id}`, { method: 'DELETE' });
    await recargarEspacio();
    mostrarToast('Documento quitado del espacio', 'success');
  } catch (err) {
    mostrarToast('Error: ' + err.message, 'danger');
  }
}

// --- Drag & drop entre secciones ---

function registrarDropzone(elemento, seccion) {
  elemento.addEventListener('dragover', (e) => { e.preventDefault(); elemento.classList.add('dragover'); });
  elemento.addEventListener('dragleave', () => elemento.classList.remove('dragover'));
  elemento.addEventListener('drop', async (e) => {
    e.preventDefault();
    elemento.classList.remove('dragover');
    const refId = e.dataTransfer.getData('application/x-espacio-ref-id');
    if (!refId) return;
    const ref = ESPACIO.documentos_ref.find((r) => r.id === parseInt(refId, 10));
    if (ref && ref.seccion !== seccion) {
      await actualizarReferencia(ref.id, { seccion });
    }
  });
}

// --- Diálogo "+ Añadir documento" ---

const dialogoAnadir = document.getElementById('dialog-anadir-documento');

async function poblarSelectAsignaturas() {
  const asignaturas = await api('/asignaturas');
  asignaturas.sort((a, b) => a.nombre.localeCompare(b.nombre));
  const select = document.getElementById('buscar-doc-asignatura');
  select.innerHTML = '<option value="">Todas</option>' +
    asignaturas.filter((a) => a.estado !== 'no_elegida')
      .map((a) => `<option value="${a.id}">${escapeHtml(a.siglas ? `${a.siglas} · ${a.nombre}` : a.nombre)}</option>`).join('');
}

document.querySelectorAll('.btn-anadir-documento').forEach((btn) => {
  btn.addEventListener('click', () => {
    seccionParaAnadir = btn.dataset.seccion;
    document.getElementById('buscar-doc-nombre').value = '';
    document.getElementById('buscar-doc-asignatura').value = '';
    document.getElementById('buscar-doc-categoria').value = '';
    document.getElementById('buscar-doc-etiqueta').value = '';
    buscarDocumentos();
    dialogoAnadir.showModal();
  });
});

document.getElementById('btn-cerrar-anadir-documento').addEventListener('click', () => dialogoAnadir.close());

async function buscarDocumentos() {
  const contenedor = document.getElementById('resultados-buscar-documento');
  contenedor.innerHTML = '<p class="ds-caption">Buscando…</p>';
  const params = new URLSearchParams({ excluir_espacio_id: ESPACIO_ID });
  const q = document.getElementById('buscar-doc-nombre').value.trim();
  const asignaturaId = document.getElementById('buscar-doc-asignatura').value;
  const categoria = document.getElementById('buscar-doc-categoria').value;
  const etiqueta = document.getElementById('buscar-doc-etiqueta').value.trim();
  if (q) params.set('q', q);
  if (asignaturaId) params.set('asignatura_id', asignaturaId);
  if (categoria) params.set('categoria', categoria);
  if (etiqueta) params.set('etiqueta', etiqueta);

  const resultados = await api(`/espacios-estudio/buscar-documentos?${params}`);
  if (resultados.length === 0) {
    contenedor.innerHTML = '<p class="ds-caption">Sin resultados.</p>';
    return;
  }
  contenedor.innerHTML = resultados.map((d) => `
    <button type="button" class="espacio-resultado-doc" data-id="${d.id}">
      <span>
        <strong>${escapeHtml(d.nombre_archivo)}</strong><br>
        <span class="ds-caption">${d.asignatura_siglas ? escapeHtml(d.asignatura_siglas) + ' · ' : ''}${escapeHtml(d.asignatura_nombre || '')}</span>
      </span>
    </button>
  `).join('');
  contenedor.querySelectorAll('.espacio-resultado-doc').forEach((btn) => {
    btn.addEventListener('click', () => anadirDocumento(parseInt(btn.dataset.id, 10)));
  });
}

['buscar-doc-nombre', 'buscar-doc-etiqueta'].forEach((id) => {
  let temporizador = null;
  document.getElementById(id).addEventListener('input', () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(buscarDocumentos, 300);
  });
});
document.getElementById('buscar-doc-asignatura').addEventListener('change', buscarDocumentos);
document.getElementById('buscar-doc-categoria').addEventListener('change', buscarDocumentos);

async function anadirDocumento(documentoId) {
  try {
    await api(`/espacios-estudio/${ESPACIO_ID}/documentos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ documento_id: documentoId, seccion: seccionParaAnadir }),
    });
    await recargarEspacio();
    await buscarDocumentos();
    mostrarToast('Documento añadido', 'success');
  } catch (err) {
    mostrarToast('Error: ' + err.message, 'danger');
  }
}

// --- Checklist: nuevo objetivo ---

document.getElementById('form-nuevo-objetivo').addEventListener('submit', async (e) => {
  e.preventDefault();
  const campo = document.getElementById('objetivo-texto');
  const texto = campo.value.trim();
  if (!texto) return;
  try {
    await api(`/espacios-estudio/${ESPACIO_ID}/objetivos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto }),
    });
    campo.value = '';
    await recargarEspacio();
  } catch (err) {
    mostrarToast('Error: ' + err.message, 'danger');
  }
});

// --- Eliminar espacio ---

document.getElementById('btn-borrar-espacio').addEventListener('click', async () => {
  if (!confirm(`¿Eliminar el espacio de estudio "${ESPACIO.nombre}"? Los documentos referenciados no se eliminan.`)) return;
  await api(`/espacios-estudio/${ESPACIO_ID}`, { method: 'DELETE' });
  window.location.href = '/vista/espacios-estudio';
});

// --- Carga inicial ---

(async function iniciar() {
  try {
    ESPACIO = await api(`/espacios-estudio/${ESPACIO_ID}`);
    renderEspacio();
    await poblarSelectAsignaturas();
  } catch (err) {
    mostrarToast('Error al cargar el espacio de estudio: ' + err.message, 'danger');
  }
})();
