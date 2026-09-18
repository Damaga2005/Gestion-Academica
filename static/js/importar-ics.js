// Importar tareas desde un .ics (Atenea/Moodle). Depende de api() y escapeHtml() de
// calendario.js. Dos pasos: analizar (solo lee) y luego importar lo marcado.

const TIPOS_ICS = { entrega: 'Entrega', tarea_general: 'Tarea general', evento: 'Evento' };
let eventosIcs = [];

function opcionesAsignatura(asignaturas, elegida) {
  return '<option value="">(ninguna)</option>' + asignaturas.map((a) =>
    `<option value="${a.id}" ${a.id === elegida ? 'selected' : ''}>${escapeHtml(a.siglas || a.nombre)}</option>`
  ).join('');
}

function pintarVistaPreviaIcs(eventos, asignaturas) {
  eventosIcs = eventos;
  const hoy = new Date().toISOString().slice(0, 10);
  const contenedor = document.getElementById('ics-vista-previa');
  if (eventos.length === 0) {
    contenedor.innerHTML = '<p class="sin-elementos">No hay eventos en el archivo.</p>';
  } else {
    contenedor.innerHTML = `<table style="width:100%;border-collapse:collapse"><tbody>${eventos.map((e, i) => `
      <tr data-i="${i}">
        <td><input type="checkbox" class="ics-check" ${e.duplicado || e.fecha < hoy ? '' : 'checked'} ${e.duplicado ? 'disabled' : ''} aria-label="Importar"></td>
        <td class="ds-caption">${e.fecha}<br>${e.hora_fin || ''}</td>
        <td><span class="ds-body">${escapeHtml(e.titulo)}</span><br><span class="ds-caption ds-text-secondary">${escapeHtml(e.curso)}${e.duplicado ? ' · ya existe' : ''}</span></td>
        <td><select class="ds-select ics-asignatura">${opcionesAsignatura(asignaturas, e.asignatura_id)}</select></td>
        <td><select class="ds-select ics-tipo">${Object.entries(TIPOS_ICS).map(([v, t]) => `<option value="${v}" ${v === e.tipo ? 'selected' : ''}>${t}</option>`).join('')}</select></td>
      </tr>`).join('')}</tbody></table>`;
  }
  actualizarBotonImportarIcs();
}

function actualizarBotonImportarIcs() {
  const marcadas = document.querySelectorAll('#ics-vista-previa .ics-check:checked').length;
  const boton = document.getElementById('ics-importar');
  boton.disabled = marcadas === 0;
  boton.textContent = marcadas ? `Importar ${marcadas} seleccionadas` : 'Importar seleccionadas';
}

document.getElementById('btn-importar-ics').addEventListener('click', () => {
  document.getElementById('ics-vista-previa').innerHTML = '';
  document.getElementById('ics-error').textContent = '';
  document.getElementById('ics-archivo').value = '';
  actualizarBotonImportarIcs();
  document.getElementById('dialog-importar-ics').showModal();
});
document.getElementById('ics-cancelar').addEventListener('click', () => document.getElementById('dialog-importar-ics').close());

document.getElementById('ics-archivo').addEventListener('change', async (e) => {
  const archivo = e.target.files[0];
  if (!archivo) return;
  document.getElementById('ics-error').textContent = '';
  const datos = new FormData();
  datos.append('archivo', archivo);
  try {
    const r = await api('/calendario/importar-ics/analizar', { method: 'POST', body: datos });
    pintarVistaPreviaIcs(r.eventos, r.asignaturas);
  } catch (err) {
    document.getElementById('ics-error').textContent = err.message;
  }
});

document.getElementById('ics-vista-previa').addEventListener('change', (e) => {
  if (e.target.classList.contains('ics-check')) actualizarBotonImportarIcs();
});

document.getElementById('ics-importar').addEventListener('click', async () => {
  const recordar = document.getElementById('ics-recordatorio').value;
  const seleccion = [...document.querySelectorAll('#ics-vista-previa tr')]
    .filter((tr) => tr.querySelector('.ics-check').checked)
    .map((tr) => {
      const e = eventosIcs[parseInt(tr.dataset.i, 10)];
      const asig = tr.querySelector('.ics-asignatura').value;
      return { titulo: e.titulo, fecha: e.fecha, hora_fin: e.hora_fin, tipo: tr.querySelector('.ics-tipo').value, asignatura_id: asig ? parseInt(asig, 10) : null, recordatorio: recordar === '' ? null : parseInt(recordar, 10) };
    });
  try {
    const r = await api('/calendario/importar-ics', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ eventos: seleccion }),
    });
    mostrarToast(`${r.creadas} tareas importadas${r.omitidas ? `, ${r.omitidas} ya existían` : ''}`, 'success');
    document.getElementById('dialog-importar-ics').close();
    await cargarDatos();
  } catch (err) {
    document.getElementById('ics-error').textContent = err.message;
  }
});
