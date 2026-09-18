from flask import Blueprint, request, jsonify

from models import db, ConfiguracionApp
from routes.errors import ApiError

configuracion_bp = Blueprint("configuracion", __name__)


def obtener_configuracion():
    """Devuelve la fila única de configuración, creándola con los valores por defecto si no existe."""
    config = db.session.get(ConfiguracionApp, 1)
    if config is None:
        config = ConfiguracionApp(id=1)
        db.session.add(config)
        db.session.commit()
    return config


@configuracion_bp.get("/configuracion")
def obtener():
    return jsonify(obtener_configuracion().to_dict())


@configuracion_bp.put("/configuracion")
def actualizar():
    config = obtener_configuracion()
    data = request.get_json(silent=True) or {}

    if "tema" in data:
        config.tema = data["tema"]
    if "dias_aviso_examen" in data:
        config.dias_aviso_examen = data["dias_aviso_examen"]
    if "dias_asignatura_abandonada" in data:
        config.dias_asignatura_abandonada = data["dias_asignatura_abandonada"]
    if "objetivo_media" in data:
        v = data["objetivo_media"]
        if v is not None and (not isinstance(v, (int, float)) or not 0 <= v <= 10):
            raise ApiError("'objetivo_media' debe estar entre 0 y 10")
        config.objetivo_media = v
    if "widgets_orden" in data:
        config.widgets_orden = ",".join(str(w).strip() for w in (data["widgets_orden"] or []) if str(w).strip())
    if "widgets_ocultos" in data:
        config.widgets_ocultos = ",".join(str(w).strip() for w in (data["widgets_ocultos"] or []) if str(w).strip()) or None

    db.session.commit()
    return jsonify(config.to_dict())
