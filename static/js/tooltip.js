/*
  Tooltip compartido (V2.3). Un único elemento reutilizado para cualquier
  elemento con [data-tooltip="texto"]: se muestra en hover/foco (teclado
  incluido) y se asocia con aria-describedby para lectores de pantalla.

  Uso: <button data-tooltip="Cambiar tema">🌙</button>
*/
(function () {
  let tooltipEl = null;
  let anclaActual = null;
  let idContador = 0;

  function crearTooltip() {
    if (tooltipEl) return tooltipEl;
    tooltipEl = document.createElement('div');
    tooltipEl.className = 'ds-tooltip';
    tooltipEl.id = 'ds-tooltip-compartido';
    tooltipEl.setAttribute('role', 'tooltip');
    document.body.appendChild(tooltipEl);
    return tooltipEl;
  }

  function posicionar(ancla) {
    const tooltip = crearTooltip();
    const rect = ancla.getBoundingClientRect();
    tooltip.style.left = '0px';
    tooltip.style.top = '0px';
    tooltip.classList.add('is-visible');
    const anchoTooltip = tooltip.offsetWidth;
    const altoTooltip = tooltip.offsetHeight;

    let top = rect.top - altoTooltip - 8;
    if (top < 4) top = rect.bottom + 8;

    let left = rect.left + rect.width / 2 - anchoTooltip / 2;
    left = Math.max(4, Math.min(left, window.innerWidth - anchoTooltip - 4));

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
  }

  function mostrar(ancla) {
    const texto = ancla.getAttribute('data-tooltip');
    if (!texto) return;
    const tooltip = crearTooltip();
    anclaActual = ancla;
    tooltip.textContent = texto;

    if (!ancla.id) ancla.id = `ds-tooltip-ancla-${++idContador}`;
    if (!ancla.hasAttribute('aria-describedby')) {
      tooltip.id = `ds-tooltip-compartido`;
      ancla.setAttribute('aria-describedby', tooltip.id);
    }

    posicionar(ancla);
  }

  function ocultar() {
    if (!tooltipEl) return;
    tooltipEl.classList.remove('is-visible');
    if (anclaActual) anclaActual.removeAttribute('aria-describedby');
    anclaActual = null;
  }

  document.addEventListener('mouseover', (e) => {
    const ancla = e.target.closest('[data-tooltip]');
    if (ancla && ancla !== anclaActual) mostrar(ancla);
  });

  document.addEventListener('mouseout', (e) => {
    const ancla = e.target.closest('[data-tooltip]');
    if (ancla && ancla === anclaActual) ocultar();
  });

  document.addEventListener('focusin', (e) => {
    const ancla = e.target.closest('[data-tooltip]');
    if (ancla) mostrar(ancla);
  });

  document.addEventListener('focusout', (e) => {
    const ancla = e.target.closest('[data-tooltip]');
    if (ancla && ancla === anclaActual) ocultar();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') ocultar();
  });

  window.addEventListener('scroll', ocultar, true);
})();
