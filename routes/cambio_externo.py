import os

from flask import Blueprint, current_app, jsonify

cambio_externo_bp = Blueprint("cambio_externo", __name__)

RUTA_SONDEO = "/bd/cambio-externo"


def _huella_bd(app):
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if not uri.startswith("sqlite:///"):
        return None
    try:
        st = os.stat(uri.replace("sqlite:///", "", 1))
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def registrar_deteccion_cambio_externo(app):
    """Guarda la huella de la BD tras cada petición propia (menos el sondeo). Si en el
    sondeo la huella del disco es otra, alguien ajeno a esta app (p. ej. Syncthing desde
    otro PC) ha tocado el archivo: la pantalla abierta puede estar desfasada."""
    from flask import request

    app.config["_BD_HUELLA"] = _huella_bd(app)

    @app.after_request
    def _recordar_huella(respuesta):
        if request.path != RUTA_SONDEO:
            app.config["_BD_HUELLA"] = _huella_bd(app)
        return respuesta


@cambio_externo_bp.get(RUTA_SONDEO)
def cambio_externo():
    return jsonify({"cambiado": _huella_bd(current_app) != current_app.config.get("_BD_HUELLA")})
