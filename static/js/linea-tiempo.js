// Línea de tiempo del cuatrimestre: clases recurrentes (barra) + exámenes/entregas
// (marcadores) por asignatura, todo en una sola vista horizontal. Sin librería de
// gráficos: posiciones en px calculadas a mano (días * ancho fijo por día).

const LT_PX_POR_DIA = 22;
const LT_ALTO_FILA = 40;

const LT_ETIQUETA_TIPO = {
  examen: 'Examen', examen_parcial: 'Parcial', examen_final: 'Final', recuperacion: 'Recuperación',
  entrega: 'Entrega', tarea_general: 'Tarea', tutoria: 'Tutoría', evento: 'Evento',
};

function ltEscapeHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto == null ? '' : texto;
  return div.innerHTML;
}

function ltDias(desde, hasta) {
  return Math.round((hasta - desde) / (1000 * 60 * 60 * 24));
}

function ltRenderCabecera(inicio, anchoTotal) {
  const cabecera = document.getElementById('lt-cabecera');
  cabecera.style.width = `${anchoTotal}px`;
  const meses = [];
  const cursor = new Date(inicio);
  cursor.setDate(1);
  cursor.setMonth(cursor.getMonth() + 1);  // primer 1-del-mes dentro (o después) del rango
  while (ltDias(inicio, cursor) * LT_PX_POR_DIA < anchoTotal) {
    meses.push(new Date(cursor));
    cursor.setMonth(cursor.getMonth() + 1);
  }
  cabecera.innerHTML = meses.map((m) => {
    const left = ltDias(inicio, m) * LT_PX_POR_DIA;
    const etiqueta = m.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' });
    return `<span class="lt-mes-tick" style="left:${left}px">${ltEscapeHtml(etiqueta)}</span>`;
  }).join('');
}

function ltRender(datos) {
  const inicio = new Date(datos.rango.inicio + 'T00:00:00');
  const fin = new Date(datos.rango.fin + 'T00:00:00');
  const hoy = new Date(datos.hoy + 'T00:00:00');
  const anchoTotal = Math.max(ltDias(inicio, fin) * LT_PX_POR_DIA, 200);

  document.getElementById('lt-vacio').style.display = datos.filas.length === 0 ? '' : 'none';
  document.getElementById('lt-wrap').style.display = datos.filas.length === 0 ? 'none' : '';
  if (datos.filas.length === 0) return;

  ltRenderCabecera(inicio, anchoTotal);

  document.getElementById('lt-etiquetas-lista').innerHTML = datos.filas.map((f) =>
    `<div class="lt-etiqueta" title="${ltEscapeHtml(f.nombre)}">${ltEscapeHtml(f.siglas || f.nombre)}</div>`
  ).join('');

  const filas = document.getElementById('lt-filas');
  filas.style.width = `${anchoTotal}px`;
  filas.style.height = `${datos.filas.length * LT_ALTO_FILA}px`;
  const marcadoresYBarras = datos.filas.map((f, i) => {
    const top = i * LT_ALTO_FILA;
    let html = '';
    if (f.barra) {
      const left = ltDias(inicio, new Date(f.barra.inicio + 'T00:00:00')) * LT_PX_POR_DIA;
      const ancho = Math.max(ltDias(new Date(f.barra.inicio + 'T00:00:00'), new Date(f.barra.fin + 'T00:00:00')) * LT_PX_POR_DIA, 2);
      html += `<div class="lt-barra" style="top:${top}px;left:${left}px;width:${ancho}px" title="${ltEscapeHtml(f.nombre)}: clases"></div>`;
    }
    html += f.marcadores.map((m) => {
      const left = ltDias(inicio, new Date(m.fecha + 'T00:00:00')) * LT_PX_POR_DIA;
      const clase = m.completada ? 'es-completada' : '';
      const etiqueta = LT_ETIQUETA_TIPO[m.tipo] || m.tipo;
      return `<a class="lt-marcador ${clase}" style="top:${top}px;left:${left}px" href="/vista/calendario?anio=${m.fecha.slice(0, 4)}&mes=${m.fecha.slice(5, 7)}" data-tooltip="${ltEscapeHtml(`${etiqueta}: ${m.titulo} (${m.fecha})`)}"></a>`;
    }).join('');
    return html;
  }).join('');
  document.getElementById('lt-marcadores-barras').innerHTML = marcadoresYBarras;

  const lineaHoy = document.getElementById('lt-hoy-linea');
  if (hoy >= inicio && hoy <= fin) {
    lineaHoy.style.left = `${ltDias(inicio, hoy) * LT_PX_POR_DIA}px`;
    lineaHoy.style.height = `${datos.filas.length * LT_ALTO_FILA}px`;
    lineaHoy.hidden = false;
  } else {
    lineaHoy.hidden = true;
  }
}

async function ltCargar() {
  try {
    const datos = await fetch('/linea-tiempo').then((r) => r.json());
    ltRender(datos);
  } catch (err) {
    mostrarToast('Error al cargar la línea de tiempo: ' + err.message, 'danger');
  }
}

ltCargar();
