// Modo examen: versión "solo lo importante" de un Espacio de Estudio — cuenta atrás,
// aula/hora y el material ⭐ destacado, sin el resto de secciones (documentos sin
// destacar, formularios de añadir...). Reutiliza la misma API que espacio-estudio-detalle.js.

async function api(path, options = {}) {
  const metodo = (options.method || 'GET').toUpperCase();
  if (metodo !== 'GET' && metodo !== 'HEAD') {
    const meta = document.querySelector('meta[name="csrf-token"]');
    options.headers = Object.assign({}, options.headers, { 'X-CSRFToken': meta ? meta.content : '' });
  }
  const res = await fetch(path, options);
  if (!res.ok) {
    let mensaje = `Error ${res.status}`;
    try { mensaje = (await res.json()).error || mensaje; } catch (e) { /* sin cuerpo JSON */ }
    throw new Error(mensaje);
  }
  return res.status === 204 ? null : res.json();
}

function escapeHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto == null ? '' : texto;
  return div.innerHTML;
}

function urlAbrirDocumento(ref) {
  const asigId = ref.documento && ref.documento.asignatura_id;
  return asigId ? `/vista/asignaturas/${asigId}?doc=${ref.documento_id}` : '#';
}

function renderDestacados(espacio) {
  const contenedor = document.getElementById('me-lista-destacados');
  const refs = espacio.documentos_ref.filter((r) => r.destacado);
  if (refs.length === 0) {
    contenedor.innerHTML = `
      <p class="ds-caption sin-elementos">
        No has marcado nada como importante todavía.
        <a href="/vista/espacios-estudio/${espacio.id}">Márcalo desde el Espacio de Estudio</a>.
      </p>`;
    return;
  }
  contenedor.innerHTML = refs.map((ref) => {
    const doc = ref.documento || {};
    return `
      <div class="me-doc-fila${ref.leido ? ' es-leido' : ''}" data-ref-id="${ref.id}">
        <input type="checkbox" class="ds-checkbox-nativo" ${ref.leido ? 'checked' : ''} aria-label="Leído">
        <a href="${urlAbrirDocumento(ref)}" class="me-doc-fila-nombre">${escapeHtml(doc.nombre_archivo || '')}</a>
      </div>
    `;
  }).join('');
  contenedor.querySelectorAll('.me-doc-fila').forEach((fila) => {
    fila.querySelector('input').addEventListener('change', async (e) => {
      await api(`/espacios-estudio/documentos/${fila.dataset.refId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ leido: e.target.checked }),
      });
      fila.classList.toggle('es-leido', e.target.checked);
    });
  });
}

function renderObjetivos(espacio) {
  const contenedor = document.getElementById('me-lista-objetivos');
  if (espacio.objetivos.length === 0) {
    contenedor.innerHTML = '<p class="ds-caption sin-elementos">Sin tareas todavía.</p>';
    return;
  }
  contenedor.innerHTML = espacio.objetivos.map((obj) => `
    <div class="espacio-objetivo-fila${obj.completada ? ' es-completada' : ''}" data-id="${obj.id}">
      <input type="checkbox" class="ds-checkbox-nativo" ${obj.completada ? 'checked' : ''}>
      <span class="ds-body espacio-objetivo-texto">${escapeHtml(obj.texto)}</span>
    </div>
  `).join('');
  contenedor.querySelectorAll('.espacio-objetivo-fila').forEach((fila) => {
    fila.querySelector('input').addEventListener('change', async (e) => {
      await api(`/espacios-estudio/objetivos/${fila.dataset.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completada: e.target.checked }),
      });
      fila.classList.toggle('es-completada', e.target.checked);
    });
  });
}

async function cargar() {
  const espacio = await api(`/espacios-estudio/${window.ESPACIO_ID}`);

  document.getElementById('titulo-pagina').textContent = `Modo examen · ${espacio.nombre} · GREELEC`;
  document.getElementById('me-asignatura').textContent = espacio.asignatura_nombre
    ? `${espacio.asignatura_siglas ? espacio.asignatura_siglas + ' · ' : ''}${espacio.asignatura_nombre}`
    : espacio.nombre;
  document.getElementById('me-volver').href = `/vista/espacios-estudio/${espacio.id}`;

  const fecha = new Date(espacio.fecha + 'T00:00:00');
  document.getElementById('me-fecha').textContent = fecha.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const dias = espacio.dias_restantes;
  const card = document.getElementById('me-cuenta-atras-card');
  card.classList.toggle('es-hoy', dias === 0);
  document.getElementById('me-dias').textContent =
    dias < 0 ? `Hace ${-dias} día${-dias !== 1 ? 's' : ''}` : dias === 0 ? '¡ES HOY!' : `Faltan ${dias} día${dias !== 1 ? 's' : ''}`;

  document.getElementById('me-hora').textContent = espacio.hora_inicio
    ? `${espacio.hora_inicio}${espacio.hora_fin ? '–' + espacio.hora_fin : ''}` : '—';
  document.getElementById('me-aula').textContent = espacio.aula || '—';
  document.getElementById('me-ubicacion').textContent = espacio.ubicacion || '—';

  renderDestacados(espacio);
  renderObjetivos(espacio);
}

document.getElementById('btn-imprimir').addEventListener('click', () => window.print());

cargar();
