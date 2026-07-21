/*
  Gestor de toasts compartido (Fase 7). Un único contenedor fijo por página;
  cada llamada a mostrarToast() añade un .ds-toast (definido en
  design-system.css) que se autodescarta a los ~3.5s o al hacer clic.

  Uso: mostrarToast('Componente eliminado'); mostrarToast('Error al guardar', 'danger');
*/
const TOASTS_MAX_VISIBLES = 4;

function mostrarToast(mensaje, variante) {
  let contenedor = document.getElementById('ds-toast-container');
  if (!contenedor) {
    contenedor = document.createElement('div');
    contenedor.id = 'ds-toast-container';
    contenedor.className = 'ds-toast-container';
    document.body.appendChild(contenedor);
  }

  const toast = document.createElement('div');
  const claseVariante = { success: 'ds-toast-success', warning: 'ds-toast-warning', danger: 'ds-toast-danger' }[variante] || '';
  toast.className = `ds-toast ${claseVariante}`.trim();
  toast.style.cursor = 'pointer';
  toast.textContent = mensaje;

  const cerrar = () => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    setTimeout(() => toast.remove(), 200);
  };
  toast.addEventListener('click', cerrar);

  // Si ya hay demasiados toasts a la vez, retira el más antiguo antes de
  // añadir el nuevo (no tiene sentido acumular sin límite).
  const existentes = contenedor.children;
  if (existentes.length >= TOASTS_MAX_VISIBLES) {
    const masAntiguo = existentes[0];
    masAntiguo.style.opacity = '0';
    masAntiguo.style.transform = 'translateY(8px)';
    setTimeout(() => masAntiguo.remove(), 200);
  }

  contenedor.appendChild(toast);
  setTimeout(cerrar, 3500);
}

/*
  Reinicia la animación de entrada .ds-fade-in en un elemento que ya la
  tenía (necesario porque re-añadir la misma clase sin forzar un reflow
  no la vuelve a disparar).
*/
function reanimar(el) {
  if (!el) return;
  el.classList.remove('ds-fade-in');
  void el.offsetWidth;
  el.classList.add('ds-fade-in');
}
