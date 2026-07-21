from datetime import datetime

from flask import Blueprint, request, jsonify
from sqlalchemy import func

from models import db, Hito
from routes.errors import ApiError

hitos_bp = Blueprint("hitos", __name__)


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        raise ApiError("'fecha' debe tener formato YYYY-MM-DD")


@hitos_bp.get("/hitos")
def listar_hitos():
    hitos = Hito.query.order_by(Hito.orden, Hito.id).all()
    return jsonify([h.to_dict() for h in hitos])


@hitos_bp.post("/hitos")
def crear_hito():
    data = request.get_json(silent=True) or {}
    if "nombre" not in data:
        raise ApiError("'nombre' es obligatorio")

    max_orden = db.session.query(func.max(Hito.orden)).scalar() or 0
    hito = Hito(
        nombre=data["nombre"],
        estado=data.get("estado", "pendiente"),
        fecha=_parse_fecha(data.get("fecha")),
        orden=data.get("orden", max_orden + 1),
    )
    db.session.add(hito)
    db.session.commit()
    return jsonify(hito.to_dict()), 201


@hitos_bp.put("/hitos/<int:hito_id>")
def actualizar_hito(hito_id):
    hito = Hito.query.get_or_404(hito_id)
    data = request.get_json(silent=True) or {}

    if "nombre" in data:
        hito.nombre = data["nombre"]
    if "estado" in data:
        hito.estado = data["estado"]
    if "fecha" in data:
        hito.fecha = _parse_fecha(data["fecha"])
    if "orden" in data:
        hito.orden = data["orden"]

    db.session.commit()
    return jsonify(hito.to_dict())


@hitos_bp.delete("/hitos/<int:hito_id>")
def borrar_hito(hito_id):
    hito = Hito.query.get_or_404(hito_id)
    db.session.delete(hito)
    db.session.commit()
    return "", 204
