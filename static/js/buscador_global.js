(function () {
  const boton = document.getElementById('btn-buscador-global');
  const overlay = document.getElementById('buscador-global-overlay');
  const input = document.getElementById('buscador-global-input');
  const btnCerrar = document.getElementById('btn-cerrar-buscador-global');
  const panel = document.getElementById('buscador-global-resultados');
  if (!overlay || !input || !panel) return;

  const SPRITE = document.querySelector('#btn-buscador-global use')
    ? document.querySelector('#btn-buscador-global use').getAttribute('href').split('#')[0]
    : '/static/vendor/lucide/sprite.svg';

  let debounceTimer = null;
  let indiceActivo = -1;
  let itemsActuales = [];
  let favoritosCache = new Set();

  const GRUPOS = [
    { clave: 'asignaturas', titulo: 'Asignaturas', icono: 'graduation-cap', tipo: 'asignatura',
      render: (a) => ({ titulo: a.nombre, contexto: null, url: a.url }) },
    { clave: 'profesores', titulo: 'Profesores', icono: 'book-open', tipo: 'profesor',
      render: (p) => ({ titulo: p.nombre, contexto: [p.rol, p.asignatura_nombre].filter(Boolean).join(' · '), url: p.url }) },
    { clave: 'documentos', titulo: 'Documentos', icono: 'file-text', tipo: 'documento',
      render: (d) => ({ titulo: d.nombre_archivo, contexto: d.etiquetas.join(', ') || null, url: d.url }) },
    { clave: 'paginas_pdf', titulo: 'Contenido de PDFs', icono: 'file-text', tipo: 'pagina_pdf',
      render: (p) => ({ titulo: `${p.nombre_archivo} — pág. ${p.numero_pagina}`, fragmento: p.fragmento, url: p.url }) },
    { clave: 'examenes', titulo: 'Exámenes', icono: 'calendar', tipo: 'examen',
      render: (t) => ({ titulo: t.titulo, contexto: t.fecha, url: t.url }) },
    { clave: 'tareas', titulo: 'Tareas', icono: 'calendar', tipo: 'tarea',
      render: (t) => ({ titulo: t.titulo, contexto: t.fecha, url: t.url }) },
    { clave: 'eventos', titulo: 'Eventos', icono: 'calendar', tipo: 'evento',
      render: (t) => ({ titulo: t.titulo, contexto: t.fecha, url: t.url }) },
    { clave: 'notas', titulo: 'Notas rápidas', icono: 'file-text', tipo: 'asignatura',
      render: (n) => ({ titulo: n.asignatura_nombre, fragmento: n.fragmento, url: n.url }) },
    { clave: 'notas_al_vuelo', titulo: 'Notas al vuelo', icono: 'pencil', tipo: 'nota_al_vuelo',
      render: (n) => ({ titulo: n.fragmento, contexto: null, url: n.url }) },
    { clave: 'etiquetas', titulo: 'Etiquetas', icono: 'tag', tipo: 'etiqueta',
      render: (e) => ({ titulo: e.etiqueta, contexto: null, url: e.url }) },
    { clave: 'hitos', titulo: 'Hitos', icono: 'star', tipo: 'hito',
      render: (h) => ({ titulo: h.nombre, contexto: h.estado, url: h.url }) },
    { clave: 'conceptos', titulo: 'Repaso', icono: 'book-check', tipo: 'concepto',
      render: (c) => ({ titulo: c.nombre, contexto: c.asignatura_nombre, url: c.url }) },
  ];

  function escapeHtml(texto) {
    const div = document.createElement('div');
    div.textContent = texto == null ? '' : texto;
    return div.innerHTML;
  }

  function claveFavorito(tipo, id) {
    return `${tipo}:${id}`;
  }

  async function cargarFavoritos() {
    try {
      const favoritos = await fetch('/busqueda/favoritos').then((r) => r.json());
      favoritosCache = new Set(favoritos.map((f) => claveFavorito(f.tipo_entidad, f.entidad_id)));
    } catch (err) {
      favoritosCache = new Set();
    }
  }

  function iconoSvg(nombre, clase) {
    return `<svg class="${clase || 'ds-icon'}"><use href="${SPRITE}#lucide-${nombre}"></use></svg>`;
  }

  function renderItem(item) {
    const puedeFavorito = item.tipo !== 'etiqueta' && item.id != null;
    const esFavorito = puedeFavorito && favoritosCache.has(claveFavorito(item.tipo, item.id));
    return `
      <a href="${item.url}" class="bg-item" data-tipo="${item.tipo}" data-id="${item.id}"
         data-url="${item.url}" data-titulo="${escapeHtml(item.titulo)}">
        <span class="bg-item-icono">${iconoSvg(item.icono)}</span>
        <span class="bg-item-texto">
          <div class="bg-item-titulo">${escapeHtml(item.titulo)}</div>
          ${item.contexto ? `<div class="bg-item-contexto">${escapeHtml(item.contexto)}</div>` : ''}
          ${item.fragmento ? `<div class="bg-item-fragmento">${escapeHtml(item.fragmento)}</div>` : ''}
        </span>
        ${puedeFavorito ? `
        <button type="button" class="bg-item-favorito ${esFavorito ? 'is-favorito' : ''}" data-tooltip="Favorito" aria-label="Favorito">
          ${iconoSvg('star', 'ds-icon ds-icon--sm')}
        </button>` : ''}
      </a>
    `;
  }

  function renderResultados(data) {
    itemsActuales = [];
    indiceActivo = -1;
    const partes = [];

    for (const grupo of GRUPOS) {
      const items = data[grupo.clave];
      if (!items || items.length === 0) continue;
      const preparados = items.map((raw) => Object.assign(
        { id: raw.id || raw.documento_id || raw.asignatura_id, tipo: grupo.tipo, icono: grupo.icono },
        grupo.render(raw),
      ));
      itemsActuales.push(...preparados);
      partes.push(`
        <div class="bg-grupo">
          <div class="bg-grupo-titulo">${grupo.titulo}</div>
          ${preparados.map(renderItem).join('')}
        </div>
      `);
    }

    panel.innerHTML = partes.length === 0
      ? '<div class="bg-vacio">Sin resultados</div>'
      : partes.join('');
    enlazarEventosResultados();
  }

  async function renderRecientesYFavoritos() {
    itemsActuales = [];
    indiceActivo = -1;
    try {
      const [recientes, favoritos] = await Promise.all([
        fetch('/busqueda/recientes').then((r) => r.json()),
        fetch('/busqueda/favoritos').then((r) => r.json()),
      ]);
      favoritosCache = new Set(favoritos.map((f) => claveFavorito(f.tipo_entidad, f.entidad_id)));

      const partes = [];
      if (recientes.length) {
        const preparados = recientes.map((r) => ({
          id: r.entidad_id, tipo: r.tipo_entidad, icono: 'clock', titulo: r.etiqueta_mostrada, url: r.url,
        }));
        itemsActuales.push(...preparados);
        partes.push(`<div class="bg-grupo"><div class="bg-grupo-titulo">Recientes</div>${preparados.map(renderItem).join('')}</div>`);
      }
      panel.innerHTML = partes.length ? partes.join('') : '<div class="bg-vacio">Escribe para buscar…</div>';
      enlazarEventosResultados();
    } catch (err) {
      panel.innerHTML = '<div class="bg-vacio">Escribe para buscar…</div>';
    }
  }

  function enlazarEventosResultados() {
    panel.querySelectorAll('.bg-item').forEach((el) => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.bg-item-favorito')) {
          e.preventDefault();
          toggleFavorito(el);
          return;
        }
        registrarReciente(el.dataset.tipo, el.dataset.id, el.dataset.titulo, el.dataset.url);
      });
    });
  }

  async function toggleFavorito(el) {
    const tipo = el.dataset.tipo;
    const id = el.dataset.id;
    const btn = el.querySelector('.bg-item-favorito');
    const meta = document.querySelector('meta[name="csrf-token"]');
    const activo = btn.classList.contains('is-favorito');
    try {
      let res;
      if (activo) {
        res = await fetch(`/busqueda/favoritos?tipo_entidad=${tipo}&entidad_id=${id}`, {
          method: 'DELETE',
          headers: { 'X-CSRFToken': meta ? meta.content : '' },
        });
        if (res.ok) favoritosCache.delete(claveFavorito(tipo, id));
      } else {
        res = await fetch('/busqueda/favoritos', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': meta ? meta.content : '' },
          body: JSON.stringify({ tipo_entidad: tipo, entidad_id: parseInt(id, 10) }),
        });
        if (res.ok) favoritosCache.add(claveFavorito(tipo, id));
      }
      if (res.ok) btn.classList.toggle('is-favorito', !activo);
    } catch (err) {
      console.warn('No se pudo actualizar el favorito:', err);
    }
  }

  function registrarReciente(tipo, id, titulo, url) {
    const meta = document.querySelector('meta[name="csrf-token"]');
    fetch('/busqueda/recientes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': meta ? meta.content : '' },
      body: JSON.stringify({ tipo_entidad: tipo, entidad_id: parseInt(id, 10), etiqueta_mostrada: titulo, url }),
    }).catch(() => {});
  }

  async function buscar(termino) {
    if (!termino || termino.trim().length < 2) {
      renderRecientesYFavoritos();
      return;
    }
    try {
      const res = await fetch(`/buscar?q=${encodeURIComponent(termino.trim())}`);
      if (!res.ok) return;
      renderResultados(await res.json());
    } catch (err) {
      console.warn('Error en la búsqueda global:', err);
    }
  }

  function abrirBuscador() {
    overlay.classList.remove('oculto');
    input.value = '';
    input.focus();
    renderRecientesYFavoritos();
  }

  function cerrarBuscador() {
    overlay.classList.add('oculto');
  }

  function moverSeleccion(delta) {
    const els = Array.from(panel.querySelectorAll('.bg-item'));
    if (els.length === 0) return;
    els[indiceActivo]?.classList.remove('is-activo');
    indiceActivo = (indiceActivo + delta + els.length) % els.length;
    els[indiceActivo].classList.add('is-activo');
    els[indiceActivo].scrollIntoView({ block: 'nearest' });
  }

  if (boton) boton.addEventListener('click', abrirBuscador);
  if (btnCerrar) btnCerrar.addEventListener('click', cerrarBuscador);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) cerrarBuscador();
  });

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const valor = input.value;
    debounceTimer = setTimeout(() => buscar(valor), 300);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); moverSeleccion(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moverSeleccion(-1); }
    else if (e.key === 'Enter') {
      const els = panel.querySelectorAll('.bg-item');
      if (indiceActivo >= 0 && els[indiceActivo]) {
        e.preventDefault();
        els[indiceActivo].click();
      }
    }
  });

  document.addEventListener('keydown', (e) => {
    const esCtrlK = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k';
    if (esCtrlK) {
      e.preventDefault();
      if (overlay.classList.contains('oculto')) abrirBuscador();
      else cerrarBuscador();
      return;
    }
    if (e.key === 'Escape' && !overlay.classList.contains('oculto')) {
      cerrarBuscador();
    }
  });
})();
