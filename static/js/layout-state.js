/*
  Persistencia de preferencias de layout (V2.3): filtros, vista lista/
  cuadrícula, etc. Generaliza el patrón ya usado a mano para
  "documentos-vista" en asignatura.js, con un prefijo común para no chocar
  con otras claves de localStorage.
*/
(function () {
  const PREFIJO = 'greelec:';

  function get(clave, porDefecto) {
    try {
      const valor = localStorage.getItem(PREFIJO + clave);
      if (valor === null) return porDefecto;
      return JSON.parse(valor);
    } catch (err) {
      return porDefecto;
    }
  }

  function set(clave, valor) {
    try {
      localStorage.setItem(PREFIJO + clave, JSON.stringify(valor));
    } catch (err) {
      // localStorage no disponible (modo privado, cuota llena...): no persistir.
    }
  }

  window.layoutState = { get, set };
})();
