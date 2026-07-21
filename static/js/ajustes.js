async function api(path, options = {}) {
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

async function cargarConfiguracion() {
  const config = await api('/configuracion');
  document.getElementById('dias-aviso-examen').value = config.dias_aviso_examen;
  document.getElementById('dias-asignatura-abandonada').value = config.dias_asignatura_abandonada;
  document.getElementById('tema-actual-texto').textContent = config.tema === 'oscuro' ? 'Oscuro' : 'Claro';
}

document.getElementById('btn-guardar-notificaciones').addEventListener('click', async (e) => {
  const boton = e.currentTarget;
  const mensaje = document.getElementById('mensaje-notificaciones');
  boton.classList.add('is-loading');
  try {
    await api('/configuracion', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dias_aviso_examen: parseInt(document.getElementById('dias-aviso-examen').value, 10),
        dias_asignatura_abandonada: parseInt(document.getElementById('dias-asignatura-abandonada').value, 10),
      }),
    });
    mensaje.textContent = 'Guardado ✓';
    mensaje.classList.remove('es-error');
    setTimeout(() => { mensaje.textContent = ''; }, 2500);
  } catch (err) {
    mensaje.textContent = 'Error: ' + err.message;
    mensaje.classList.add('es-error');
  } finally {
    boton.classList.remove('is-loading');
  }
});

document.getElementById('btn-cambiar-tema-ajustes').addEventListener('click', () => {
  document.getElementById('toggle-tema').click();
  setTimeout(() => {
    const tema = document.documentElement.getAttribute('data-theme');
    document.getElementById('tema-actual-texto').textContent = tema === 'oscuro' ? 'Oscuro' : 'Claro';
  }, 50);
});

document.getElementById('form-importar-backup').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('input-backup');
  const mensaje = document.getElementById('mensaje-backup');
  if (!input.files.length) return;

  const confirmado = confirm(
    'Importar un backup SOBRESCRIBIRÁ toda tu base de datos y documentos actuales con lo que haya en el .zip. ' +
    'Esta acción no se puede deshacer. ¿Seguro que quieres continuar?'
  );
  if (!confirmado) return;

  const formData = new FormData();
  formData.append('backup', input.files[0]);
  const boton = e.submitter || e.target.querySelector('button[type="submit"]');
  boton.classList.add('is-loading');

  mensaje.textContent = 'Restaurando...';
  mensaje.classList.remove('es-error');
  try {
    const data = await api('/backup/importar', { method: 'POST', body: formData });
    mensaje.textContent = data.mensaje;
    input.value = '';
  } catch (err) {
    mensaje.textContent = 'Error: ' + err.message;
    mensaje.classList.add('es-error');
  } finally {
    boton.classList.remove('is-loading');
  }
});

cargarConfiguracion();
