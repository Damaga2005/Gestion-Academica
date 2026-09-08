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

function nbRenderLista(notificaciones) {
  const lista = document.getElementById('nb-lista');
  if (notificaciones.length === 0) {
    lista.innerHTML = '<p class="ds-caption ds-text-secondary nb-vacio">Sin avisos.</p>';
    return;
  }
  lista.innerHTML = notificaciones.map((n) => `
    <a class="nb-item" href="${n.url}">
      <span class="ds-badge ${NB_BADGE_POR_NIVEL[n.nivel] || 'ds-badge'}">&nbsp;</span>
      <span class="nb-item-texto">
        <span class="nb-item-titulo">${nbEscapeHtml(n.titulo)}</span>
        <span class="ds-caption ds-text-secondary">${nbEscapeHtml(n.mensaje)}</span>
      </span>
    </a>
  `).join('');
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
