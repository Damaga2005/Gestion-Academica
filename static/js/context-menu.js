/*
  Menú contextual compartido (V2.3). Un único menú reutilizado por toda la
  app: click derecho o un botón "..." pueden abrirlo con abrirMenuContextual.
  role="menu"/"menuitem", navegación con flechas, Enter/Espacio para activar,
  Escape/click-fuera para cerrar con devolución de foco al elemento que lo abrió.

  Uso:
    elemento.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      abrirMenuContextual([
        { etiqueta: 'Abrir', accion: () => abrir() },
        { etiqueta: 'Eliminar', accion: () => eliminar(), peligroso: true },
      ], { x: e.clientX, y: e.clientY });
    });
*/
(function () {
  let menuEl = null;
  let indiceActivo = -1;
  let elementoQueAbrio = null;

  function cerrarMenuContextual() {
    if (!menuEl) return;
    menuEl.remove();
    menuEl = null;
    indiceActivo = -1;
    document.removeEventListener('click', cerrarSiFuera, true);
    document.removeEventListener('keydown', gestionarTeclado, true);
    if (elementoQueAbrio && elementoQueAbrio.focus) elementoQueAbrio.focus();
    elementoQueAbrio = null;
  }

  function cerrarSiFuera(e) {
    if (menuEl && !menuEl.contains(e.target)) cerrarMenuContextual();
  }

  function items() {
    return menuEl ? Array.from(menuEl.querySelectorAll('.ds-context-menu-item')) : [];
  }

  function moverSeleccion(delta) {
    const els = items();
    if (els.length === 0) return;
    els[indiceActivo]?.classList.remove('is-activo');
    indiceActivo = (indiceActivo + delta + els.length) % els.length;
    els[indiceActivo].classList.add('is-activo');
    els[indiceActivo].focus();
  }

  function gestionarTeclado(e) {
    if (!menuEl) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      cerrarMenuContextual();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      moverSeleccion(1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      moverSeleccion(-1);
    } else if (e.key === 'Tab') {
      cerrarMenuContextual();
    }
  }

  function escapeHtml(texto) {
    const div = document.createElement('div');
    div.textContent = texto == null ? '' : texto;
    return div.innerHTML;
  }

  function abrirMenuContextual(entradas, opciones) {
    cerrarMenuContextual();
    const { x, y, anclaEl } = opciones || {};
    elementoQueAbrio = (anclaEl || document.activeElement);

    menuEl = document.createElement('div');
    menuEl.className = 'ds-context-menu';
    menuEl.setAttribute('role', 'menu');

    entradas.forEach((entrada) => {
      if (entrada.separador) {
        const sep = document.createElement('div');
        sep.className = 'ds-context-menu-separador';
        sep.setAttribute('role', 'separator');
        menuEl.appendChild(sep);
        return;
      }
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('role', 'menuitem');
      btn.className = `ds-context-menu-item${entrada.peligroso ? ' ds-context-menu-item--peligroso' : ''}`;
      btn.innerHTML = escapeHtml(entrada.etiqueta);
      btn.addEventListener('click', () => {
        cerrarMenuContextual();
        entrada.accion();
      });
      menuEl.appendChild(btn);
    });

    document.body.appendChild(menuEl);

    // Posicionar y ajustar dentro del viewport antes de mostrar.
    const ancho = menuEl.offsetWidth;
    const alto = menuEl.offsetHeight;
    const left = Math.max(4, Math.min(x, window.innerWidth - ancho - 4));
    const top = Math.max(4, Math.min(y, window.innerHeight - alto - 4));
    menuEl.style.left = `${left}px`;
    menuEl.style.top = `${top}px`;
    requestAnimationFrame(() => menuEl && menuEl.classList.add('is-visible'));

    setTimeout(() => document.addEventListener('click', cerrarSiFuera, true), 0);
    document.addEventListener('keydown', gestionarTeclado, true);

    const primero = menuEl.querySelector('.ds-context-menu-item');
    if (primero) {
      indiceActivo = 0;
      primero.classList.add('is-activo');
      primero.focus();
    }
  }

  window.abrirMenuContextual = abrirMenuContextual;
  window.cerrarMenuContextual = cerrarMenuContextual;
})();
