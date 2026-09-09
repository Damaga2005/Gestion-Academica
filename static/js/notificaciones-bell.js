// Campanita de avisos (ver templates/_notificaciones_bell.html): consume el mismo
// GET /notificaciones que ya usaba el toast nativo de Windows al arrancar, pero
// visible en cualquier momento desde cualquier página, sin tener que reiniciar la app.

const NB_BADGE_POR_NIVEL = { rojo: 'ds-badge-danger', naranja: 'ds-badge-warning', gris: 'ds-badge' };
const NB_TITULO_ORIGINAL = document.title;

function nbEscapeHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto == null ? '' : texto;
  return div.innerHTML;
}

async function nbDescartar(tipo, entidadId) {
  const meta = document.querySelector('meta[name="csrf-token"]');
  await fetch('/notificaciones/descartar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': meta ? meta.content : '' },
    body: JSON.stringify({ tipo, entidad_id: entidadId }),
  });
}

function nbRenderLista(notificaciones) {
  const lista = document.getElementById('nb-lista');
  if (notificaciones.length === 0) {
    lista.innerHTML = '<p class="ds-caption ds-text-secondary nb-vacio">Sin avisos.</p>';
    return;
  }
  lista.innerHTML = notificaciones.map((n) => `
    <div class="nb-item" data-tipo="${n.tipo}" data-entidad-id="${n.entidad_id}">
      <a class="nb-item-link" href="${n.url}">
        <span class="ds-badge ${NB_BADGE_POR_NIVEL[n.nivel] || 'ds-badge'}">&nbsp;</span>
        <span class="nb-item-texto">
          <span class="nb-item-titulo">${nbEscapeHtml(n.titulo)}</span>
          <span class="ds-caption ds-text-secondary">${nbEscapeHtml(n.mensaje)}</span>
        </span>
      </a>
      <button type="button" class="nb-item-descartar" title="Descartar por hoy" aria-label="Descartar por hoy">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
      </button>
    </div>
  `).join('');
  lista.querySelectorAll('.nb-item-descartar').forEach((boton) => {
    boton.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const fila = boton.closest('.nb-item');
      await nbDescartar(fila.dataset.tipo, Number(fila.dataset.entidadId));
      nbCargar();
    });
  });
}

async function nbCargar() {
  const badge = document.getElementById('nb-badge');
  try {
    const notificaciones = await (await fetch('/notificaciones')).json();
    if (notificaciones.length > 0) {
      badge.textContent = notificaciones.length > 9 ? '9+' : String(notificaciones.length);
      badge.hidden = false;
      badge.classList.toggle('nb-badge--urgente', notificaciones.some((n) => n.nivel === 'rojo'));
      document.title = `(${notificaciones.length}) ${NB_TITULO_ORIGINAL}`;
    } else {
      badge.hidden = true;
      document.title = NB_TITULO_ORIGINAL;
    }
    nbRenderLista(notificaciones);
  } catch (err) {
    badge.hidden = true;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const boton = document.getElementById('btn-notificaciones-bell');
  const dropdown = document.getElementById('nb-dropdown');
  if (!boton || !dropdown) return; // página sin el include (no debería pasar, defensivo)

  nbCargar();

  boton.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.hidden = !dropdown.hidden;
  });
  document.addEventListener('click', (e) => {
    if (!dropdown.hidden && !dropdown.contains(e.target) && e.target !== boton) {
      dropdown.hidden = true;
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') dropdown.hidden = true;
  });
});
