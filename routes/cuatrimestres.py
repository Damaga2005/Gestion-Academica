from flask import Blueprint, request, jsonify

from models import db, Cuatrimestre, Anio
from routes.errors import ApiError

cuatrimestres_bp = Blueprint("cuatrimestres", __name__)


@cuatrimestres_bp.get("/cuatrimestres")
def listar_cuatrimestres():
    query = Cuatrimestre.query
    anio_id = request.args.get("anio_id", type=int)
    if anio_id is not None:
        query = query.filter_by(anio_id=anio_id)
    cuatrimestres = query.order_by(Cuatrimestre.numero).all()
    return jsonify([c.to_dict(include_asignaturas=False) for c in cuatrimestres])


@cuatrimestres_bp.get("/cuatrimestres/<int:cuatrimestre_id>")
def obtener_cuatrimestre(cuatrimestre_id):
    cuatrimestre = Cuatrimestre.query.get_or_404(cuatrimestre_id)
    return jsonify(cuatrimestre.to_dict(include_asignaturas=True))


@cuatrimestres_bp.post("/cuatrimestres")
def crear_cuatrimestre():
    data = request.get_json(silent=True) or {}
    for campo in ("anio_id", "numero"):
        if campo not in data:
            raise ApiError(f"'{campo}' es obligatorio")

    Anio.query.get_or_404(data["anio_id"])

    cuatrimestre = Cuatrimestre(
        anio_id=data["anio_id"],
        numero=data["numero"],
        estado=data.get("estado", "pendiente"),
    )
    db.session.add(cuatrimestre)
    db.session.commit()
    return jsonify(cuatrimestre.to_dict()), 201


@cuatrimestres_bp.put("/cuatrimestres/<int:cuatrimestre_id>")
def actualizar_cuatrimestre(cuatrimestre_id):
    cuatrimestre = Cuatrimestre.query.get_or_404(cuatrimestre_id)
    data = request.get_json(silent=True) or {}

    if "anio_id" in data:
        Anio.query.get_or_404(data["anio_id"])
        cuatrimestre.anio_id = data["anio_id"]
    if "numero" in data:
        cuatrimestre.numero = data["numero"]
    if "estado" in data:
        cuatrimestre.estado = data["estado"]

    db.session.commit()
    return jsonify(cuatrimestre.to_dict())


@cuatrimestres_bp.delete("/cuatrimestres/<int:cuatrimestre_id>")
def borrar_cuatrimestre(cuatrimestre_id):
    cuatrimestre = Cuatrimestre.query.get_or_404(cuatrimestre_id)
    db.session.delete(cuatrimestre)
    db.session.commit()
    return "", 204
