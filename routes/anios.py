from flask import Blueprint, request, jsonify

from models import db, Anio
from routes.errors import ApiError

anios_bp = Blueprint("anios", __name__)


@anios_bp.get("/anios")
def listar_anios():
    anios = Anio.query.order_by(Anio.numero).all()
    return jsonify([a.to_dict() for a in anios])


@anios_bp.get("/anios/<int:anio_id>")
def obtener_anio(anio_id):
    anio = Anio.query.get_or_404(anio_id)
    return jsonify(anio.to_dict(include_cuatrimestres=True))


@anios_bp.post("/anios")
def crear_anio():
    data = request.get_json(silent=True) or {}
    if "numero" not in data:
        raise ApiError("'numero' es obligatorio")
    anio = Anio(numero=data["numero"])
    db.session.add(anio)
    db.session.commit()
    return jsonify(anio.to_dict()), 201


@anios_bp.put("/anios/<int:anio_id>")
def actualizar_anio(anio_id):
    anio = Anio.query.get_or_404(anio_id)
    data = request.get_json(silent=True) or {}
    if "numero" in data:
        anio.numero = data["numero"]
    db.session.commit()
    return jsonify(anio.to_dict())


@anios_bp.delete("/anios/<int:anio_id>")
def borrar_anio(anio_id):
    anio = Anio.query.get_or_404(anio_id)
    db.session.delete(anio)
    db.session.commit()
    return "", 204
