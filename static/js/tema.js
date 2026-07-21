(function () {
  const boton = document.getElementById('toggle-tema');
  if (!boton) return;

  function actualizarIcono(tema) {
    boton.textContent = tema === 'oscuro' ? '☀️' : '🌙'; // ☀️ / 🌙
    boton.title = tema === 'oscuro' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
  }

  actualizarIcono(document.documentElement.getAttribute('data-theme') || 'oscuro');

  boton.addEventListener('click', async () => {
    const actual = document.documentElement.getAttribute('data-theme') || 'oscuro';
    const nuevo = actual === 'oscuro' ? 'claro' : 'oscuro';

    document.documentElement.setAttribute('data-theme', nuevo);
    actualizarIcono(nuevo);

    try {
      const meta = document.querySelector('meta[name="csrf-token"]');
      await fetch('/configuracion', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': meta ? meta.content : '' },
        body: JSON.stringify({ tema: nuevo }),
      });
    } catch (err) {
      console.warn('No se pudo guardar la preferencia de tema:', err);
    }
  });
})();
