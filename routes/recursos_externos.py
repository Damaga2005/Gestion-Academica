from flask import Blueprint, request, jsonify
from sqlalchemy import func

from models import db, RecursoExterno, Asignatura
from routes.errors import ApiError

recursos_externos_bp = Blueprint("recursos_externos", __name__)


@recursos_externos_bp.get("/asignaturas/<int:asignatura_id>/recursos-externos")
def listar_recursos(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    recursos = RecursoExterno.query.filter_by(asignatura_id=asignatura_id).order_by(RecursoExterno.orden).all()
    return jsonify([r.to_dict() for r in recursos])


@recursos_externos_bp.post("/asignaturas/<int:asignatura_id>/recursos-externos")
def crear_recurso(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}
    for campo in ("nombre", "url"):
        if campo not in data:
            raise ApiError(f"'{campo}' es obligatorio")

    max_orden = db.session.query(func.max(RecursoExterno.orden)).filter_by(asignatura_id=asignatura_id).scalar() or 0
    recurso = RecursoExterno(
        asignatura_id=asignatura_id,
        nombre=data["nombre"],
        url=data["url"],
        tipo=data.get("tipo"),
        orden=data.get("orden", max_orden + 1),
    )
    db.session.add(recurso)
    db.session.commit()
    return jsonify(recurso.to_dict()), 201


@recursos_externos_bp.put("/recursos-externos/<int:recurso_id>")
def actualizar_recurso(recurso_id):
    recurso = RecursoExterno.query.get_or_404(recurso_id)
    data = request.get_json(silent=True) or {}

    if "nombre" in data:
        recurso.nombre = data["nombre"]
    if "url" in data:
        recurso.url = data["url"]
    if "tipo" in data:
        recurso.tipo = data["tipo"]
    if "orden" in data:
        recurso.orden = data["orden"]

    db.session.commit()
    return jsonify(recurso.to_dict())


@recursos_externos_bp.delete("/recursos-externos/<int:recurso_id>")
def borrar_recurso(recurso_id):
    recurso = RecursoExterno.query.get_or_404(recurso_id)
    db.session.delete(recurso)
    db.session.commit()
    return "", 204
