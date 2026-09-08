// Notas rápidas (ver templates/_notas_rapidas.html): bloc de notas accesible desde
// cualquier página, para apuntar algo al vuelo sin perder de vista lo que se mira.

function nrEscapeHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto == null ? '' : texto;
  return div.innerHTML;
}

async function nrApi(path, options = {}) {
  const metodo = (options.method || 'GET').toUpperCase();
  if (metodo !== 'GET' && metodo !== 'HEAD') {
    const meta = document.querySelector('meta[name="csrf-token"]');
    options.headers = Object.assign({}, options.headers, { 'X-CSRFToken': meta ? meta.content : '' });
  }
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.status === 204 ? null : res.json();
}

function nrRenderLista(notas) {
  const lista = document.getElementById('nr-lista');
  if (notas.length === 0) {
    lista.innerHTML = '<p class="ds-caption ds-text-secondary nb-vacio">Sin notas todavía.</p>';
    return;
  }
  lista.innerHTML = notas.map((n) => `
    <div class="nr-item" data-id="${n.id}">
      <span class="nr-item-texto">${nrEscapeHtml(n.texto)}</span>
      <button type="button" class="nr-item-borrar" title="Borrar" aria-label="Borrar nota">
        <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-x"></use></svg>
      </button>
    </div>
  `).join('');
  lista.querySelectorAll('.nr-item-borrar').forEach((boton) => {
    boton.addEventListener('click', async () => {
      const id = boton.closest('.nr-item').dataset.id;
      await nrApi(`/notas-rapidas/${id}`, { method: 'DELETE' });
      nrCargar();
    });
  });
}

async function nrCargar() {
  try {
    nrRenderLista(await nrApi('/notas-rapidas'));
  } catch (err) {
    document.getElementById('nr-lista').innerHTML = '<p class="ds-caption nb-vacio">Error al cargar.</p>';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const boton = document.getElementById('btn-notas-rapidas');
  const dropdown = document.getElementById('nr-dropdown');
  const form = document.getElementById('nr-form');
  if (!boton || !dropdown || !form) return; // página sin el include (defensivo)

  boton.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.hidden = !dropdown.hidden;
    if (!dropdown.hidden) nrCargar();
  });
  document.addEventListener('click', (e) => {
    if (!dropdown.hidden && !dropdown.contains(e.target) && e.target !== boton) {
      dropdown.hidden = true;
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') dropdown.hidden = true;
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const campo = document.getElementById('nr-texto');
    const texto = campo.value.trim();
    if (!texto) return;
    await nrApi('/notas-rapidas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto }),
    });
    campo.value = '';
    nrCargar();
  });
});
