/* Capa de anotaciones estilo Acrobat para el visor pdf.js.
 *
 * Se carga dentro del iframe de viewer.html y añade:
 *   - barra flotante al seleccionar texto (copiar / resaltar / subrayar / tachar / nota),
 *   - la misma barra al hacer clic derecho sobre una selección, que es la vía de
 *     copiar que espera cualquiera y que no depende del menú contextual nativo
 *     del contenedor de escritorio,
 *   - anotaciones persistentes por documento, que se repintan al hacer zoom.
 *
 * La geometría se guarda normalizada (0..1 respecto de la página), así que al
 * cambiar el zoom basta con volver a pintar: no hay recálculo de coordenadas.
 *
 * CSP de viewer.html: `style-src 'self'` prohíbe atributos style="" en el HTML,
 * pero no tocar `elemento.style.*` desde JS, que es lo que se hace aquí.
 */
(function () {
  'use strict';

  const COLORES = ['#ffd400', '#4ade80', '#60a5fa', '#f472b6', '#fb923c', '#e11d48'];
  const CLAVE_COLOR = 'greelec.pdf.color';

  let app = null;
  let documentoId = null;
  let colorActual = COLORES[0];

  /** numeroPagina -> lista de anotaciones de esa página. */
  const porPagina = new Map();

  let barra = null;
  let ficha = null;
  let aviso = null;
  let temporizadorAviso = null;
  let seleccion = null; // resultado de leerSeleccion() congelado al abrir la barra
  let anotacionAbierta = null;

  // --- utilidades -----------------------------------------------------------

  function tokenCsrf() {
    try {
      const meta = window.parent.document.querySelector('meta[name="csrf-token"]');
      if (meta) return meta.content;
    } catch (err) {
      // El visor abierto directamente (fuera del iframe de la app) no tiene
      // acceso al documento padre. Se sigue sin token: solo fallarían los POST.
    }
    return '';
  }

  async function api(url, opciones) {
    const cfg = Object.assign({}, opciones);
    cfg.headers = Object.assign(
      { 'Content-Type': 'application/json', 'X-CSRFToken': tokenCsrf() },
      cfg.headers || {}
    );
    const res = await fetch(url, cfg);
    if (!res.ok) throw new Error(`${res.status} en ${url}`);
    return res.status === 204 ? null : res.json();
  }

  function detectarDocumentoId() {
    const file = new URLSearchParams(window.location.search).get('file') || '';
    let ruta = file;
    try {
      ruta = decodeURIComponent(file);
    } catch (err) {
      // file mal codificado: se busca sobre la cadena original
    }
    const encontrado = ruta.match(/\/documentos\/(\d+)\/archivo/);
    return encontrado ? Number(encontrado[1]) : null;
  }

  function mostrarAviso(texto) {
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.hidden = false;
    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(() => { aviso.hidden = true; }, 1600);
  }

  async function copiarAlPortapapeles(texto) {
    if (!texto) return;
    try {
      await navigator.clipboard.writeText(texto);
    } catch (err) {
      // navigator.clipboard puede no estar disponible según el contenedor;
      // el textarea temporal + execCommand funciona en todos los casos.
      const campo = document.createElement('textarea');
      campo.value = texto;
      campo.style.position = 'fixed';
      campo.style.opacity = '0';
      document.body.appendChild(campo);
      campo.select();
      try {
        document.execCommand('copy');
      } finally {
        campo.remove();
      }
    }
    mostrarAviso('Texto copiado');
  }

  // --- geometría ------------------------------------------------------------

  /** Caja de referencia de una página: la misma que usa la capa de texto de
   *  pdf.js (inset:0 dentro del div de página), para que las coordenadas
   *  normalizadas de una selección y las de pintado coincidan exactamente. */
  function cajaDePagina(numero) {
    const vista = app.pdfViewer.getPageView(numero - 1);
    if (!vista || !vista.div) return null;
    const ref = vista.div.querySelector('.textLayer') || vista.div.querySelector('.canvasWrapper');
    return ref ? ref.getBoundingClientRect() : null;
  }

  /** Solo las páginas ya renderizadas tienen capa de texto; el resto no puede
   *  contener ni una selección ni un clic sobre una anotación. */
  function paginasRenderizadas() {
    const lista = [];
    const total = app.pdfViewer.pagesCount || 0;
    for (let numero = 1; numero <= total; numero++) {
      const caja = cajaDePagina(numero);
      if (caja && caja.width > 0 && caja.height > 0) lista.push({ numero, caja });
    }
    return lista;
  }

  /** Une los rectángulos sueltos de la selección (uno por span de pdf.js) en
   *  una barra por línea de texto, que es como se ve en cualquier lector. */
  function fusionarPorLineas(rects) {
    const lineas = [];
    const ordenados = rects
      .map((r) => ({ left: r.left, top: r.top, right: r.right, bottom: r.bottom }))
      .sort((a, b) => a.top - b.top || a.left - b.left);

    for (const r of ordenados) {
      const alto = r.bottom - r.top;
      const linea = lineas.find((l) => {
        const solape = Math.min(l.bottom, r.bottom) - Math.max(l.top, r.top);
        return solape > 0.5 * Math.min(l.bottom - l.top, alto);
      });
      if (linea) {
        linea.left = Math.min(linea.left, r.left);
        linea.right = Math.max(linea.right, r.right);
        linea.top = Math.min(linea.top, r.top);
        linea.bottom = Math.max(linea.bottom, r.bottom);
      } else {
        lineas.push(Object.assign({}, r));
      }
    }
    return lineas;
  }

  function leerSeleccion() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) return null;
    const texto = sel.toString().trim();
    if (!texto) return null;

    const paginas = paginasRenderizadas();
    const rectsPorPagina = new Map();
    let encuadre = null;

    for (let i = 0; i < sel.rangeCount; i++) {
      for (const rect of sel.getRangeAt(i).getClientRects()) {
        if (rect.width < 1 || rect.height < 1) continue;
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const pagina = paginas.find(
          (p) => cx >= p.caja.left && cx <= p.caja.right && cy >= p.caja.top && cy <= p.caja.bottom
        );
        if (!pagina) continue;
        if (!rectsPorPagina.has(pagina.numero)) {
          rectsPorPagina.set(pagina.numero, { caja: pagina.caja, rects: [] });
        }
        rectsPorPagina.get(pagina.numero).rects.push(rect);
        encuadre = encuadre
          ? {
              left: Math.min(encuadre.left, rect.left),
              top: Math.min(encuadre.top, rect.top),
              right: Math.max(encuadre.right, rect.right),
              bottom: Math.max(encuadre.bottom, rect.bottom),
            }
          : { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom };
      }
    }

    if (rectsPorPagina.size === 0) return null;
    return { texto, rectsPorPagina, encuadre };
  }

  function normalizar(caja, linea) {
    return [
      (linea.left - caja.left) / caja.width,
      (linea.top - caja.top) / caja.height,
      (linea.right - linea.left) / caja.width,
      (linea.bottom - linea.top) / caja.height,
    ];
  }

  // --- pintado --------------------------------------------------------------

  function pintarPagina(numero) {
    // Las coordenadas guardadas son relativas a la página sin girar; con el
    // documento rotado no encajarían, así que no se pinta nada.
    if (app.pdfViewer.pagesRotation) return;

    const vista = app.pdfViewer.getPageView(numero - 1);
    if (!vista || !vista.div) return;

    const lista = porPagina.get(numero) || [];
    let capa = vista.div.querySelector('.ga-anot-layer');
    if (!capa) {
      if (!lista.length) return;
      capa = document.createElement('div');
      capa.className = 'ga-anot-layer';
      vista.div.appendChild(capa);
    }
    capa.textContent = '';

    for (const anot of lista) {
      anot.rects.forEach((rect, indice) => {
        const [x, y, ancho, alto] = rect;
        const el = document.createElement('div');
        el.className = `ga-anot ga-anot--${anot.tipo}`;
        el.style.setProperty('--ga-color', anot.color);
        el.style.left = `${x * 100}%`;
        el.style.top = `${y * 100}%`;
        el.style.width = `${ancho * 100}%`;
        el.style.height = `${alto * 100}%`;
        if (anot.tipo === 'subrayado' || anot.tipo === 'tachado') {
          const barraLinea = document.createElement('div');
          barraLinea.className = 'ga-anot-barra';
          el.appendChild(barraLinea);
        }
        if (anot.comentario && indice === anot.rects.length - 1) {
          const globo = document.createElement('div');
          globo.className = 'ga-anot-globo';
          globo.textContent = '!';
          globo.style.left = '100%';
          globo.style.top = '0';
          el.appendChild(globo);
        }
        capa.appendChild(el);
      });
    }
  }

  function repintarTodo() {
    for (const numero of porPagina.keys()) pintarPagina(numero);
  }

  function registrar(anotacion) {
    const lista = porPagina.get(anotacion.numero_pagina) || [];
    const indice = lista.findIndex((a) => a.id === anotacion.id);
    if (indice >= 0) lista[indice] = anotacion;
    else lista.push(anotacion);
    porPagina.set(anotacion.numero_pagina, lista);
  }

  function olvidar(anotacion) {
    const lista = porPagina.get(anotacion.numero_pagina) || [];
    porPagina.set(
      anotacion.numero_pagina,
      lista.filter((a) => a.id !== anotacion.id)
    );
  }

  function avisarAlPadre() {
    // La app aloja el visor en un iframe y muestra su propia lista de
    // anotaciones; se le avisa para que la recargue.
    try {
      window.parent.postMessage(
        { tipo: 'greelec:anotaciones-cambiadas', documentoId },
        window.location.origin
      );
    } catch (err) {
      // Sin padre accesible no hay nada que refrescar.
    }
  }

  // --- barra de selección ---------------------------------------------------

  function crearBoton(texto, titulo, alPulsar) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = texto;
    b.title = titulo;
    b.addEventListener('click', alPulsar);
    return b;
  }

  function filaDeColores(alElegir, obtenerActual) {
    const fila = document.createElement('div');
    fila.className = 'ga-colores';
    for (const color of COLORES) {
      const punto = document.createElement('button');
      punto.type = 'button';
      punto.className = 'ga-color';
      punto.title = color;
      punto.style.backgroundColor = color;
      punto.addEventListener('click', () => {
        alElegir(color);
        for (const otro of fila.children) {
          otro.classList.toggle('is-activo', otro === punto);
        }
      });
      fila.appendChild(punto);
    }
    const marcar = () => {
      const actual = obtenerActual();
      Array.from(fila.children).forEach((punto, i) => {
        punto.classList.toggle('is-activo', COLORES[i] === actual);
      });
    };
    marcar();
    fila.sincronizar = marcar;
    return fila;
  }

  function construirBarra() {
    barra = document.createElement('div');
    barra.className = 'ga-barra';
    barra.hidden = true;

    // mousedown en la barra no debe deshacer la selección del documento.
    barra.addEventListener('mousedown', (e) => e.preventDefault());

    barra.appendChild(
      crearBoton('Copiar', 'Copiar el texto seleccionado (Ctrl+C)', () => {
        if (seleccion) copiarAlPortapapeles(seleccion.texto);
        ocultarBarra();
      })
    );

    const sep = document.createElement('div');
    sep.className = 'ga-barra-sep';
    barra.appendChild(sep);

    barra.appendChild(crearBoton('Resaltar', 'Resaltar la selección', () => crearDesdeSeleccion('resaltado')));
    barra.appendChild(crearBoton('Subrayar', 'Subrayar la selección', () => crearDesdeSeleccion('subrayado')));
    barra.appendChild(crearBoton('Tachar', 'Tachar la selección', () => crearDesdeSeleccion('tachado')));
    barra.appendChild(crearBoton('Nota', 'Resaltar y añadir un comentario', () => crearDesdeSeleccion('nota')));

    const sep2 = document.createElement('div');
    sep2.className = 'ga-barra-sep';
    barra.appendChild(sep2);

    barra.appendChild(
      filaDeColores(
        (color) => {
          colorActual = color;
          try {
            localStorage.setItem(CLAVE_COLOR, color);
          } catch (err) {
            // localStorage no disponible: el color simplemente no se recuerda.
          }
        },
        () => colorActual
      )
    );

    document.body.appendChild(barra);
  }

  function colocarFlotante(elemento, encuadre) {
    elemento.hidden = false;
    const propio = elemento.getBoundingClientRect();
    const margen = 8;

    let izquierda = encuadre.left + (encuadre.right - encuadre.left) / 2 - propio.width / 2;
    izquierda = Math.min(Math.max(margen, izquierda), window.innerWidth - propio.width - margen);

    let arriba = encuadre.top - propio.height - margen;
    if (arriba < margen) arriba = encuadre.bottom + margen;
    arriba = Math.min(arriba, window.innerHeight - propio.height - margen);

    elemento.style.left = `${Math.round(izquierda)}px`;
    elemento.style.top = `${Math.round(arriba)}px`;
  }

  function mostrarBarra(datos) {
    seleccion = datos;
    cerrarFicha();
    for (const hijo of barra.children) {
      if (hijo.sincronizar) hijo.sincronizar();
    }
    colocarFlotante(barra, datos.encuadre);
  }

  function ocultarBarra() {
    if (barra) barra.hidden = true;
    seleccion = null;
  }

  async function crearDesdeSeleccion(tipo) {
    const datos = seleccion;
    if (!datos) return;
    ocultarBarra();

    let ultima = null;
    try {
      for (const [numero, info] of datos.rectsPorPagina) {
        const rects = fusionarPorLineas(info.rects).map((linea) => normalizar(info.caja, linea));
        const creada = await api(`/documentos/${documentoId}/anotaciones`, {
          method: 'POST',
          body: JSON.stringify({
            numero_pagina: numero,
            tipo,
            color: colorActual,
            texto: datos.texto,
            rects,
          }),
        });
        registrar(creada);
        pintarPagina(numero);
        ultima = creada;
      }
    } catch (err) {
      mostrarAviso('No se pudo guardar la anotación');
      return;
    }

    const sel = window.getSelection();
    if (sel) sel.removeAllRanges();
    avisarAlPadre();

    if (tipo === 'nota' && ultima) abrirFicha(ultima, encuadreDeAnotacion(ultima));
  }

  // --- ficha de una anotación existente -------------------------------------

  function encuadreDeAnotacion(anotacion) {
    const caja = cajaDePagina(anotacion.numero_pagina);
    if (!caja) return { left: 0, top: 0, right: 0, bottom: 0 };
    let encuadre = null;
    for (const [x, y, ancho, alto] of anotacion.rects) {
      const r = {
        left: caja.left + x * caja.width,
        top: caja.top + y * caja.height,
        right: caja.left + (x + ancho) * caja.width,
        bottom: caja.top + (y + alto) * caja.height,
      };
      encuadre = encuadre
        ? {
            left: Math.min(encuadre.left, r.left),
            top: Math.min(encuadre.top, r.top),
            right: Math.max(encuadre.right, r.right),
            bottom: Math.max(encuadre.bottom, r.bottom),
          }
        : r;
    }
    return encuadre || { left: 0, top: 0, right: 0, bottom: 0 };
  }

  function construirFicha() {
    ficha = document.createElement('div');
    ficha.className = 'ga-ficha';
    ficha.hidden = true;
    ficha.addEventListener('mousedown', (e) => e.stopPropagation());
    document.body.appendChild(ficha);
  }

  function cerrarFicha() {
    if (ficha) ficha.hidden = true;
    anotacionAbierta = null;
  }

  function abrirFicha(anotacion, encuadre) {
    ocultarBarra();
    anotacionAbierta = anotacion;
    ficha.textContent = '';

    if (anotacion.texto) {
      const cita = document.createElement('div');
      cita.className = 'ga-ficha-texto';
      cita.textContent = `“${anotacion.texto}”`;
      ficha.appendChild(cita);
    }

    const comentario = document.createElement('textarea');
    comentario.placeholder = 'Comentario (se guarda al salir del campo)';
    comentario.value = anotacion.comentario || '';
    comentario.addEventListener('change', async () => {
      try {
        const actualizada = await api(`/anotaciones/${anotacion.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ comentario: comentario.value }),
        });
        registrar(actualizada);
        pintarPagina(actualizada.numero_pagina);
        avisarAlPadre();
      } catch (err) {
        mostrarAviso('No se pudo guardar el comentario');
      }
    });
    ficha.appendChild(comentario);

    const fila = document.createElement('div');
    fila.className = 'ga-ficha-fila';
    fila.appendChild(
      filaDeColores(
        async (color) => {
          try {
            const actualizada = await api(`/anotaciones/${anotacion.id}`, {
              method: 'PATCH',
              body: JSON.stringify({ color }),
            });
            registrar(actualizada);
            anotacionAbierta = actualizada;
            pintarPagina(actualizada.numero_pagina);
            avisarAlPadre();
          } catch (err) {
            mostrarAviso('No se pudo cambiar el color');
          }
        },
        () => (anotacionAbierta || anotacion).color
      )
    );

    const acciones = document.createElement('div');
    acciones.className = 'ga-ficha-acciones';
    acciones.appendChild(
      crearBoton('Copiar', 'Copiar el texto de la anotación', () => {
        copiarAlPortapapeles(anotacion.texto || '');
      })
    );
    const borrar = crearBoton('Eliminar', 'Eliminar la anotación', async () => {
      try {
        await api(`/anotaciones/${anotacion.id}`, { method: 'DELETE' });
        olvidar(anotacion);
        pintarPagina(anotacion.numero_pagina);
        cerrarFicha();
        avisarAlPadre();
      } catch (err) {
        mostrarAviso('No se pudo eliminar la anotación');
      }
    });
    borrar.classList.add('ga-ficha-borrar');
    acciones.appendChild(borrar);
    fila.appendChild(acciones);
    ficha.appendChild(fila);

    colocarFlotante(ficha, encuadre);
  }

  function anotacionEnPunto(x, y) {
    for (const { numero, caja } of paginasRenderizadas()) {
      if (x < caja.left || x > caja.right || y < caja.top || y > caja.bottom) continue;
      const nx = (x - caja.left) / caja.width;
      const ny = (y - caja.top) / caja.height;
      const lista = porPagina.get(numero) || [];
      for (let i = lista.length - 1; i >= 0; i--) {
        for (const [rx, ry, ancho, alto] of lista[i].rects) {
          if (nx >= rx && nx <= rx + ancho && ny >= ry && ny <= ry + alto) return lista[i];
        }
      }
    }
    return null;
  }

  // --- arranque -------------------------------------------------------------

  function engancharEventos() {
    const contenedor = document.getElementById('viewerContainer') || document;

    document.addEventListener('mouseup', (evento) => {
      // Soltar el ratón sobre la propia barra o la ficha no es una selección
      // nueva: si se recalculara aquí, la barra reaparecería justo después de
      // que su botón la haya cerrado.
      if (barra && barra.contains(evento.target)) return;
      if (ficha && ficha.contains(evento.target)) return;
      // En el mismo tick la selección aún puede estar a medias en algunos
      // navegadores; se lee en el siguiente.
      setTimeout(() => {
        const datos = leerSeleccion();
        if (datos) mostrarBarra(datos);
        else ocultarBarra();
      }, 0);
    });

    document.addEventListener('contextmenu', (evento) => {
      const datos = leerSeleccion();
      if (!datos) return; // sin selección se deja el menú que haya
      // Con selección se ofrece la barra propia: el contenedor de escritorio
      // puede no tener menú contextual nativo, y "clic derecho → Copiar" tiene
      // que funcionar igualmente.
      evento.preventDefault();
      mostrarBarra(Object.assign({}, datos, {
        encuadre: { left: evento.clientX, top: evento.clientY, right: evento.clientX, bottom: evento.clientY },
      }));
    });

    document.addEventListener('click', (evento) => {
      if (barra && !barra.hidden && barra.contains(evento.target)) return;
      if (ficha && !ficha.hidden && ficha.contains(evento.target)) return;

      const sel = window.getSelection();
      if (sel && !sel.isCollapsed) return; // se está seleccionando texto

      const anotacion = anotacionEnPunto(evento.clientX, evento.clientY);
      if (anotacion) abrirFicha(anotacion, encuadreDeAnotacion(anotacion));
      else cerrarFicha();
    });

    document.addEventListener('keydown', (evento) => {
      if (evento.key === 'Escape') {
        ocultarBarra();
        cerrarFicha();
      }
    });

    // Las flotantes van en coordenadas de ventana: al desplazar el documento
    // dejarían de apuntar a su sitio, así que se cierran.
    contenedor.addEventListener('scroll', () => {
      ocultarBarra();
      cerrarFicha();
    });
    window.addEventListener('resize', () => {
      ocultarBarra();
      cerrarFicha();
    });

    app.eventBus.on('textlayerrendered', (evt) => pintarPagina(evt.pageNumber));
    app.eventBus.on('pagerendered', (evt) => pintarPagina(evt.pageNumber));
    app.eventBus.on('scalechanging', () => {
      ocultarBarra();
      cerrarFicha();
    });
    app.eventBus.on('rotationchanging', () => {
      // Con la página girada las coordenadas normalizadas ya no encajan; se
      // limpian las capas para no pintar barras descolocadas.
      document.querySelectorAll('.ga-anot-layer').forEach((capa) => capa.remove());
    });
  }

  async function cargarAnotaciones() {
    // Se limpian las capas ya pintadas antes de recargar: si una anotación se
    // ha borrado, su página deja de estar en el mapa y no se repintaría sola.
    document.querySelectorAll('.ga-anot-layer').forEach((capa) => capa.remove());
    porPagina.clear();
    if (!documentoId) return;
    try {
      const lista = await api(`/documentos/${documentoId}/anotaciones`);
      for (const anotacion of lista) registrar(anotacion);
      repintarTodo();
    } catch (err) {
      // Sin anotaciones cargadas el visor sigue siendo perfectamente usable.
      console.warn('No se pudieron cargar las anotaciones del PDF:', err);
    }
  }

  function arrancar() {
    documentoId = detectarDocumentoId();

    try {
      const guardado = localStorage.getItem(CLAVE_COLOR);
      if (guardado && COLORES.includes(guardado)) colorActual = guardado;
    } catch (err) {
      // localStorage no disponible: se usa el color por defecto.
    }

    aviso = document.createElement('div');
    aviso.className = 'ga-aviso';
    aviso.hidden = true;
    document.body.appendChild(aviso);

    construirBarra();
    construirFicha();
    engancharEventos();

    app.eventBus.on('documentloaded', cargarAnotaciones);
    if (app.pdfDocument) cargarAnotaciones();

    // La app que aloja el iframe la usa para refrescar tras borrar desde su
    // propio panel de anotaciones.
    window.greelecAnotaciones = { recargar: cargarAnotaciones };
  }

  function esperarAPdfJs() {
    app = window.PDFViewerApplication;
    if (!app || !app.initializedPromise) {
      setTimeout(esperarAPdfJs, 50);
      return;
    }
    app.initializedPromise.then(arrancar);
  }

  esperarAPdfJs();
})();
