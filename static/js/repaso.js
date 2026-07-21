const NOMBRES_ESTADO_CONCEPTO = { no_visto: 'No visto', flojo: 'Flojo', dominado: 'Dominado' };

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

async function cargarRepaso() {
  const conceptos = await api('/repaso-hoy');
  const contenedor = document.getElementById('repaso-contenedor');

  if (conceptos.length === 0) {
    contenedor.innerHTML = `
      <div class="ds-card">
        <div class="ds-empty-state">
          <div class="ds-empty-state-icon">🎉</div>
          <div class="ds-empty-state-title">Nada que repasar hoy</div>
          <p class="ds-empty-state-description">Vuelve mañana para ver los próximos conceptos.</p>
        </div>
      </div>
    `;
    return;
  }

  const porAsignatura = {};
  for (const c of conceptos) {
    const clave = c.asignatura_nombre || 'Sin asignatura';
    (porAsignatura[clave] = porAsignatura[clave] || []).push(c);
  }

  contenedor.innerHTML = '';
  for (const [nombreAsignatura, lista] of Object.entries(porAsignatura)) {
    const seccion = document.createElement('section');
    seccion.className = 'grupo-repaso ds-card';
    seccion.innerHTML = `<h3 class="ds-h3">${escapeHtml(nombreAsignatura)}</h3><ul class="lista-conceptos"></ul>`;
    const ul = seccion.querySelector('ul');

    for (const c of lista) {
      const li = document.createElement('li');
      li.innerHTML = `
        <span class="concepto-nombre">${escapeHtml(c.nombre)}</span>
        <span class="badge estado-concepto-${c.estado}">${NOMBRES_ESTADO_CONCEPTO[c.estado]}</span>
        <button type="button" class="btn-bajar-concepto" title="Bajar de nivel" aria-label="Bajar de nivel">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-arrow-down"></use></svg>
        </button>
        <button type="button" class="btn-subir-concepto" title="Subir de nivel" aria-label="Subir de nivel">
          <svg class="ds-icon"><use href="/static/vendor/lucide/sprite.svg#lucide-arrow-up"></use></svg>
        </button>
      `;
      li.querySelector('.btn-subir-concepto').addEventListener('click', async () => {
        await api(`/conceptos/${c.id}/subir`, { method: 'POST' });
        await cargarRepaso();
      });
      li.querySelector('.btn-bajar-concepto').addEventListener('click', async () => {
        await api(`/conceptos/${c.id}/bajar`, { method: 'POST' });
        await cargarRepaso();
      });
      ul.appendChild(li);
    }

    contenedor.appendChild(seccion);
  }
  reanimar(contenedor);
}

cargarRepaso();
