/*
  Atajos de teclado globales (V2.3). Navegación estilo Gmail: "g" seguido de
  una letra. Se ignoran todos los atajos mientras el foco esté en un campo de
  formulario (salvo Escape, que ya gestiona cada página/componente por su
  cuenta). "?" abre un panel de ayuda con el registro de atajos, usando el
  <dialog class="ds-modal"> ya existente en el design system.
*/
(function () {
  const RUTAS = {
    d: { destino: '/vista/dashboard', etiqueta: 'Resumen' },
    a: { destino: '/vista', etiqueta: 'Asignaturas' },
    c: { destino: '/vista/calendario', etiqueta: 'Calendario' },
    h: { destino: '/vista/horario', etiqueta: 'Horario' },
    r: { destino: '/vista/repaso', etiqueta: 'Repaso' },
    s: { destino: '/vista/ajustes', etiqueta: 'Configuración' },
  };

  const ATAJOS_AYUDA = [
    { teclas: ['Ctrl', 'K'], descripcion: 'Buscar en toda la app' },
    { teclas: ['g', 'd'], descripcion: 'Ir a Resumen' },
    { teclas: ['g', 'a'], descripcion: 'Ir a Asignaturas' },
    { teclas: ['g', 'c'], descripcion: 'Ir a Calendario' },
    { teclas: ['g', 'h'], descripcion: 'Ir a Horario' },
    { teclas: ['g', 'r'], descripcion: 'Ir a Repaso' },
    { teclas: ['g', 's'], descripcion: 'Ir a Configuración' },
    { teclas: ['n'], descripcion: 'Nueva nota al vuelo' },
    { teclas: ['?'], descripcion: 'Mostrar esta ayuda' },
    { teclas: ['Esc'], descripcion: 'Cerrar ventana/menú activo' },
  ];

  let esperandoG = false;
  let timeoutG = null;

  function enCampoDeFormulario(el) {
    if (!el) return false;
    const tag = el.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
  }

  function crearDialogoAyuda() {
    let dialogo = document.getElementById('ds-dialogo-atajos');
    if (dialogo) return dialogo;

    dialogo = document.createElement('dialog');
    dialogo.id = 'ds-dialogo-atajos';
    dialogo.className = 'ds-modal';
    dialogo.innerHTML = `
      <h2 class="ds-h2">Atajos de teclado</h2>
      <ul class="ds-atajos-lista">
        ${ATAJOS_AYUDA.map((a) => `
          <li class="ds-atajos-item">
            <span class="ds-body">${a.descripcion}</span>
            <span class="ds-atajos-teclas">
              ${a.teclas.map((t) => `<kbd class="ds-atajos-tecla">${t}</kbd>`).join('')}
            </span>
          </li>
        `).join('')}
      </ul>
    `;
    document.body.appendChild(dialogo);
    return dialogo;
  }

  function abrirAyuda() {
    const dialogo = crearDialogoAyuda();
    if (typeof dialogo.showModal === 'function') dialogo.showModal();
  }

  function irA(ruta) {
    if (window.location.pathname !== ruta) window.location.href = ruta;
  }

  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (enCampoDeFormulario(e.target)) return;

    if (esperandoG) {
      esperandoG = false;
      clearTimeout(timeoutG);
      const ruta = RUTAS[e.key.toLowerCase()];
      if (ruta) {
        e.preventDefault();
        irA(ruta.destino);
      }
      return;
    }

    if (e.key === 'g' || e.key === 'G') {
      esperandoG = true;
      timeoutG = setTimeout(() => { esperandoG = false; }, 1200);
      return;
    }

    if (e.key === '?') {
      e.preventDefault();
      abrirAyuda();
      return;
    }

    if (e.key === 'n') {
      const boton = document.getElementById('btn-notas-rapidas');
      const dropdown = document.getElementById('nr-dropdown');
      const campo = document.getElementById('nr-texto');
      if (!boton || !dropdown || !campo) return; // página sin _notas_rapidas.html (defensivo)
      e.preventDefault();
      if (dropdown.hidden) boton.click();
      campo.focus();
    }
  });
})();
