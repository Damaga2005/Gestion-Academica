(function () {
  const input = document.getElementById('buscador-input');
  const panel = document.getElementById('buscador-resultados');
  if (!input || !panel) return;

  let debounceTimer = null;

  function escapeHtml(texto) {
    const div = document.createElement('div');
    div.textContent = texto == null ? '' : texto;
    return div.innerHTML;
  }

  function renderGrupo(titulo, items, renderItem) {
    if (!items || items.length === 0) return '';
    return `
      <div class="buscador-grupo">
        <h4>${titulo}</h4>
        <ul>${items.map(renderItem).join('')}</ul>
      </div>
    `;
  }

  function renderResultados(data) {
    const partes = [
      renderGrupo('Asignaturas', data.asignaturas, (a) =>
        `<li><a href="${a.url}">${escapeHtml(a.nombre)}</a></li>`),
      renderGrupo('Documentos', data.documentos, (d) =>
        `<li><a href="${d.url}">${escapeHtml(d.nombre_archivo)}</a>${
          d.etiquetas.length ? ' <span class="mini-tags">' + d.etiquetas.map(escapeHtml).join(', ') + '</span>' : ''
        }</li>`),
      renderGrupo('En el contenido de PDFs', data.paginas_pdf, (p) =>
        `<li><a href="${p.url}">${escapeHtml(p.nombre_archivo)} — pág. ${p.numero_pagina}</a>
          <div class="fragmento">${escapeHtml(p.fragmento)}</div></li>`),
      renderGrupo('Notas rápidas', data.notas, (n) =>
        `<li><a href="${n.url}">${escapeHtml(n.asignatura_nombre)}</a>
          <div class="fragmento">${escapeHtml(n.fragmento)}</div></li>`),
      renderGrupo('Tareas/eventos', data.tareas, (t) =>
        `<li><a href="${t.url}">${escapeHtml(t.titulo)} (${t.fecha})</a></li>`),
    ].filter(Boolean);

    panel.innerHTML = partes.length === 0
      ? '<div class="buscador-vacio">Sin resultados</div>'
      : partes.join('');
    panel.classList.remove('oculto');
  }

  async function buscar(termino) {
    if (!termino || termino.trim().length < 2) {
      panel.classList.add('oculto');
      return;
    }
    try {
      const res = await fetch(`/buscar?q=${encodeURIComponent(termino.trim())}`);
      if (!res.ok) return;
      renderResultados(await res.json());
    } catch (err) {
      console.warn('Error en la búsqueda:', err);
    }
  }

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const valor = input.value;
    debounceTimer = setTimeout(() => buscar(valor), 300);
  });

  input.addEventListener('focus', () => {
    if (input.value.trim().length >= 2) panel.classList.remove('oculto');
  });

  document.addEventListener('click', (e) => {
    if (e.target !== input && !panel.contains(e.target)) {
      panel.classList.add('oculto');
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') panel.classList.add('oculto');
  });
})();
