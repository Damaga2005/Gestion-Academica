from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from models import db, Asignatura, SesionEstudio, registrar_actividad_hoy
from routes.errors import ApiError

estudio_bp = Blueprint("estudio", __name__)


@estudio_bp.post("/estudio/sesiones")
def registrar_sesion():
    """Guarda una sesión del temporizador y cuenta como día de estudio para la racha."""
    data = request.get_json(silent=True) or {}
    minutos = data.get("minutos")
    if not isinstance(minutos, int) or not 1 <= minutos <= 600:
        raise ApiError("'minutos' debe ser un entero entre 1 y 600")
    asignatura_id = data.get("asignatura_id")
    if asignatura_id is not None and db.session.get(Asignatura, asignatura_id) is None:
        raise ApiError("asignatura no encontrada")

    db.session.add(SesionEstudio(asignatura_id=asignatura_id, minutos=minutos))
    registrar_actividad_hoy()
    db.session.commit()
    return jsonify(_resumen()), 201


def _resumen():
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())

    def total(desde):
        return db.session.query(func.coalesce(func.sum(SesionEstudio.minutos), 0)).filter(SesionEstudio.fecha >= desde).scalar()

    por_asignatura = (
        db.session.query(Asignatura.siglas, Asignatura.nombre, func.sum(SesionEstudio.minutos))
        .join(SesionEstudio, SesionEstudio.asignatura_id == Asignatura.id)
        .filter(SesionEstudio.fecha >= lunes)
        .group_by(Asignatura.id).order_by(func.sum(SesionEstudio.minutos).desc()).all()
    )
    return {
        "hoy_min": total(hoy),
        "semana_min": total(lunes),
        "por_asignatura": [{"asignatura": siglas or nombre, "minutos": int(m)} for siglas, nombre, m in por_asignatura],
    }


@estudio_bp.get("/estudio/resumen")
def resumen():
    return jsonify(_resumen())
