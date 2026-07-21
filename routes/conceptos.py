from datetime import date

from flask import Blueprint, request, jsonify

from models import db, Concepto, Asignatura
from routes.errors import ApiError

conceptos_bp = Blueprint("conceptos", __name__)


@conceptos_bp.get("/asignaturas/<int:asignatura_id>/conceptos")
def listar_conceptos(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    conceptos = Concepto.query.filter_by(asignatura_id=asignatura_id).order_by(Concepto.nombre).all()
    return jsonify([c.to_dict() for c in conceptos])


@conceptos_bp.post("/asignaturas/<int:asignatura_id>/conceptos")
def crear_concepto(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}
    if "nombre" not in data:
        raise ApiError("'nombre' es obligatorio")

    concepto = Concepto(
        asignatura_id=asignatura_id,
        nombre=data["nombre"],
        estado="no_visto",
        proxima_revision=date.today(),  # un concepto recién añadido toca repasarlo ya
    )
    db.session.add(concepto)
    db.session.commit()
    return jsonify(concepto.to_dict()), 201


@conceptos_bp.put("/conceptos/<int:concepto_id>")
def actualizar_concepto(concepto_id):
    concepto = Concepto.query.get_or_404(concepto_id)
    data = request.get_json(silent=True) or {}
    if "nombre" in data:
        concepto.nombre = data["nombre"]
    db.session.commit()
    return jsonify(concepto.to_dict())


@conceptos_bp.delete("/conceptos/<int:concepto_id>")
def borrar_concepto(concepto_id):
    concepto = Concepto.query.get_or_404(concepto_id)
    db.session.delete(concepto)
    db.session.commit()
    return "", 204


@conceptos_bp.post("/conceptos/<int:concepto_id>/subir")
def subir_concepto(concepto_id):
    concepto = Concepto.query.get_or_404(concepto_id)
    concepto.reclasificar(1)
    db.session.commit()
    return jsonify(concepto.to_dict())


@conceptos_bp.post("/conceptos/<int:concepto_id>/bajar")
def bajar_concepto(concepto_id):
    concepto = Concepto.query.get_or_404(concepto_id)
    concepto.reclasificar(-1)
    db.session.commit()
    return jsonify(concepto.to_dict())


@conceptos_bp.get("/repaso-hoy")
def repaso_hoy():
    hoy = date.today()
    conceptos = (
        Concepto.query.filter(Concepto.proxima_revision <= hoy)
        .join(Asignatura)
        .order_by(Asignatura.nombre, Concepto.nombre)
        .all()
    )
    return jsonify([c.to_dict() for c in conceptos])
