"""
Punto de entrada para ejecutar la app como ventana de escritorio nativa (Fase 6),
en vez de abrirla en el navegador.

El servidor Flask escucha por defecto solo en 127.0.0.1 (acceso exclusivo desde
este equipo). El acceso desde el móvil por red local es opcional: para activarlo
hay que definir explícitamente GREELEC_HOST=0.0.0.0 en el .env, nunca por defecto.
"""

import os
import socket
import threading
import time

import webview

from app import create_app
from config import RESOURCE_DIR

HOST = os.environ.get("GREELEC_HOST", "127.0.0.1")
PUERTO = int(os.environ.get("GREELEC_PORT", "5000"))
ICONO = os.path.join(RESOURCE_DIR, "icono.ico")

# Entradas del menú contextual de WebView2 que se conservan al hacer clic derecho.
# El resto (recargar, atrás/adelante, ver código fuente, inspeccionar, compartir…)
# se quita porque son opciones de navegador, no de una app de escritorio.
MENU_CONTEXTUAL_PERMITIDO = {
    "copy",
    "cut",
    "paste",
    "selectAll",
    "undo",
    "redo",
    "print",
    "copyImage",
    "saveImageAs",
    "copyLinkLocation",
}


def _filtrar_menu_contextual(sender, args):
    try:
        items = args.MenuItems
        for i in range(items.Count - 1, -1, -1):
            if items[i].Name not in MENU_CONTEXTUAL_PERMITIDO:
                items.RemoveAt(i)
    except Exception:  # pragma: no cover - depende del runtime de WebView2
        # Si el filtrado falla se deja el menú completo: es preferible un menú
        # con opciones de más que quedarse sin "Copiar".
        pass


def _habilitar_copiar_y_atajos():
    """Reactiva el menú contextual y los atajos de teclado del navegador.

    pywebview solo los habilita cuando se arranca en modo debug
    (`AreDefaultContextMenusEnabled`/`AreBrowserAcceleratorKeysEnabled` se
    asignan desde `_state['debug']`), así que en la app empaquetada el clic
    derecho no ofrece "Copiar" y Ctrl+F / Ctrl+P / Ctrl+±  no hacen nada. Eso
    deja el visor de PDF sin la forma habitual de copiar texto, buscar o
    imprimir, que es justo lo que se espera de un lector de PDF.

    Se parchea `on_webview_ready` en vez de tocar los ajustes desde fuera
    porque ese método se ejecuta en el hilo de la interfaz y justo después de
    que pywebview aplique su propia configuración.
    """
    try:
        from webview.platforms import edgechromium
    except Exception as exc:  # pragma: no cover - backend no disponible
        print(f"No se pudo ajustar WebView2 (se sigue sin el cambio): {exc}")
        return

    original = edgechromium.EdgeChrome.on_webview_ready

    def on_webview_ready(self, sender, args):
        original(self, sender, args)
        try:
            core = sender.CoreWebView2
            core.Settings.AreDefaultContextMenusEnabled = True
            core.Settings.AreBrowserAcceleratorKeysEnabled = True
            core.ContextMenuRequested += _filtrar_menu_contextual
        except Exception as exc:  # pragma: no cover - depende del runtime
            print(f"No se pudo ajustar WebView2 (se sigue sin el cambio): {exc}")

    edgechromium.EdgeChrome.on_webview_ready = on_webview_ready


def _avisar_notificaciones_urgentes(app):
    """Aviso nativo de Windows al arrancar: GET /notificaciones (routes/notificaciones.py)
    ya calculaba tareas atrasadas/inminentes y asignaturas cursando sin actividad, pero
    no había ningún sitio en la UI donde verlas. Solo se muestra un toast por arranque,
    y solo con los avisos nivel rojo (lo urgente de verdad), para no ser spam.
    """
    try:
        from winotify import Notification
    except Exception as exc:  # pragma: no cover - opcional, no debe impedir arrancar la app
        print(f"No se pudo cargar winotify (sin avisos nativos): {exc}")
        return

    with app.app_context():
        from routes.notificaciones import calcular_notificaciones
        urgentes = [n for n in calcular_notificaciones() if n["nivel"] == "rojo"]

    if not urgentes:
        return

    if len(urgentes) == 1:
        mensaje = urgentes[0]["mensaje"]
    else:
        mensaje = f"{len(urgentes)} avisos urgentes: " + "; ".join(n["titulo"] for n in urgentes[:3])

    try:
        Notification(
            app_id="GestionAcademicaGREELEC",
            title="GREELEC",
            msg=mensaje,
            duration="long",
            icon=ICONO if os.path.isfile(ICONO) else "",
        ).show()
    except Exception as exc:
        # ponytail: el toast nativo de Windows depende de un AUMID registrado; sin
        # empaquetado MSIX/firma puede fallar en silencio en alguna máquina. Si eso
        # pasa de forma consistente, el upgrade real es empaquetar con MSIX.
        print(f"No se pudo mostrar el aviso nativo: {exc}")


def _iniciar_servidor(app):
    # debug=False y use_reloader=False: el reloader de Flask (que relanza el
    # proceso) no es compatible con ejecutar Flask dentro de un hilo de la app.
    app.run(host=HOST, port=PUERTO, debug=False, use_reloader=False)


def _esperar_servidor(host="127.0.0.1", port=PUERTO, timeout=10):
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main():
    # create_app() aplica las migraciones pendientes, y eso puede tardar bastante en
    # el primer arranque tras una actualización. Se hace aquí, en el hilo principal y
    # ANTES de montar el servidor, para que no compita con el temporizador de
    # _esperar_servidor(): si la migración corriera dentro del hilo daemon y se
    # agotara la espera, el proceso moriría a media migración y dejaría la base de
    # datos a medias (en SQLite el DDL ya está confirmado y no se puede revertir).
    app = create_app()

    hilo_servidor = threading.Thread(target=_iniciar_servidor, args=(app,), daemon=True)
    hilo_servidor.start()

    if not _esperar_servidor():
        raise RuntimeError("El servidor Flask no arrancó a tiempo")

    _habilitar_copiar_y_atajos()
    _avisar_notificaciones_urgentes(app)

    # ALLOW_DOWNLOADS: sin esto el botón de guardar/descargar del visor de PDF
    # no hace nada.
    webview.settings["ALLOW_DOWNLOADS"] = True

    webview.create_window(
        "Gestión Académica GREELEC",
        f"http://127.0.0.1:{PUERTO}/vista/dashboard",
        width=1280,
        height=850,
        min_size=(900, 600),
        # Por defecto pywebview inyecta `body { user-select: none }`, que impide
        # seleccionar (y por tanto copiar) cualquier texto de la aplicación.
        text_select=True,
    )
    webview.start(icon=ICONO if os.path.isfile(ICONO) else None)


if __name__ == "__main__":
    main()
