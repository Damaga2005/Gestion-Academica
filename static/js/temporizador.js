// Temporizador de estudio del Resumen. Depende de api(), mostrarToast() y cargarRacha()
// de dashboard.js. Cada sesión terminada se guarda en el servidor (cuenta para la racha).
// Si sales de la página con el reloj en marcha, esa sesión no se guarda (se avisa antes).

let tempCorriendo = false;
let tempRestanteMs = 0;
let tempFinTs = 0;
let tempDuracionMs = 0;
let tempIntervalo = null;

const tempEl = (id) => document.getElementById(id);

function tempFormato(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function tempMinutosConfigurados() {
  const m = parseInt(tempEl('temp-minutos').value, 10);
  return Number.isNaN(m) ? 25 : Math.min(Math.max(m, 1), 180);
}

function tempPintar() {
  const ms = tempCorriendo ? tempFinTs - Date.now() : tempRestanteMs;
  const empezada = tempDuracionMs !== 0;
  tempEl('temp-tiempo').textContent = tempFormato(ms);
  tempEl('temp-iniciar').textContent = tempCorriendo ? 'Pausar' : (empezada ? 'Reanudar' : 'Iniciar');
  tempEl('temp-terminar').disabled = !empezada;
  tempEl('temp-minutos').disabled = empezada;
  tempEl('temp-asignatura').disabled = empezada;
}

function tempReiniciar() {
  clearInterval(tempIntervalo);
  tempCorriendo = false;
  tempDuracionMs = 0;
  tempRestanteMs = tempMinutosConfigurados() * 60000;
  tempPintar();
}

async function tempGuardar(minutos) {
  const asig = tempEl('temp-asignatura').value;
  try {
    await api('/estudio/sesiones', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ minutos, asignatura_id: asig ? parseInt(asig, 10) : null }),
    });
    mostrarToast(`Sesión de ${minutos} min guardada`, 'success');
    cargarRacha();
    await tempCargarResumen();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
}

async function tempTick() {
  if (tempFinTs - Date.now() > 0) return tempPintar();
  const minutos = Math.round(tempDuracionMs / 60000);
  clearInterval(tempIntervalo);
  tempCorriendo = false;
  await tempGuardar(minutos);
  tempReiniciar();
}

function tempAlternar() {
  if (tempCorriendo) {
    tempRestanteMs = tempFinTs - Date.now();
    tempCorriendo = false;
    clearInterval(tempIntervalo);
  } else {
    if (tempDuracionMs === 0) {
      tempDuracionMs = tempMinutosConfigurados() * 60000;
      tempRestanteMs = tempDuracionMs;
    }
    tempFinTs = Date.now() + tempRestanteMs;
    tempCorriendo = true;
    tempIntervalo = setInterval(tempTick, 500);
  }
  tempPintar();
}

async function tempTerminarYGuardar() {
  const transcurrido = tempDuracionMs - (tempCorriendo ? tempFinTs - Date.now() : tempRestanteMs);
  const minutos = Math.floor(transcurrido / 60000);
  clearInterval(tempIntervalo);
  tempCorriendo = false;
  if (minutos < 1) mostrarToast('Menos de 1 minuto: no se guarda', 'info');
  else await tempGuardar(minutos);
  tempReiniciar();
}

function tempTexto(min) {
  return min >= 60 ? `${Math.floor(min / 60)} h ${min % 60} min` : `${min} min`;
}

async function tempCargarResumen() {
  try {
    const r = await api('/estudio/resumen');
    const top = r.por_asignatura.slice(0, 3).map((a) => `${escapeHtml(a.asignatura)} ${tempTexto(a.minutos)}`).join(' · ');
    tempEl('temp-resumen').innerHTML = `Hoy: <strong>${tempTexto(r.hoy_min)}</strong> · Esta semana: <strong>${tempTexto(r.semana_min)}</strong>${top ? ` (${top})` : ''}`;
  } catch (err) { /* sin resumen */ }
}

async function tempCargarAsignaturas() {
  try {
    const asignaturas = await api('/asignaturas?estado=cursando');
    tempEl('temp-asignatura').innerHTML = '<option value="">(sin asignatura)</option>' +
      asignaturas.map((a) => `<option value="${a.id}">${escapeHtml(a.siglas || a.nombre)}</option>`).join('');
  } catch (err) { /* sin lista */ }
}

tempEl('temp-iniciar').addEventListener('click', tempAlternar);
tempEl('temp-terminar').addEventListener('click', tempTerminarYGuardar);
tempEl('temp-minutos').addEventListener('input', () => { if (tempDuracionMs === 0) tempReiniciar(); });
window.addEventListener('beforeunload', (e) => { if (tempCorriendo) { e.preventDefault(); e.returnValue = ''; } });

// "Mi semana" en papel: solo la sección de la semana (ver dashboard.css @media print).
tempEl('btn-imprimir-semana').addEventListener('click', () => {
  document.body.classList.add('imprimiendo-semana');
  window.print();
});
window.addEventListener('afterprint', () => document.body.classList.remove('imprimiendo-semana'));

tempReiniciar();
tempCargarAsignaturas();
tempCargarResumen();
