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

    webview.create_window(
        "Gestión Académica GREELEC",
        f"http://127.0.0.1:{PUERTO}/vista/dashboard",
        width=1280,
        height=850,
        min_size=(900, 600),
    )
    webview.start(icon=ICONO if os.path.isfile(ICONO) else None)


if __name__ == "__main__":
    main()
