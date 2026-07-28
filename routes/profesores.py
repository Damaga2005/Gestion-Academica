from flask import Blueprint, request, jsonify
from sqlalchemy import func

from models import db, Profesor, Asignatura
from routes.errors import ApiError

profesores_bp = Blueprint("profesores", __name__)


@profesores_bp.get("/asignaturas/<int:asignatura_id>/profesores")
def listar_profesores(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    profesores = Profesor.query.filter_by(asignatura_id=asignatura_id).order_by(Profesor.orden).all()
    return jsonify([p.to_dict() for p in profesores])


@profesores_bp.post("/asignaturas/<int:asignatura_id>/profesores")
def crear_profesor(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}
    if not data.get("nombre"):
        raise ApiError("'nombre' es obligatorio")

    max_orden = db.session.query(func.max(Profesor.orden)).filter_by(asignatura_id=asignatura_id).scalar() or 0
    profesor = Profesor(
        asignatura_id=asignatura_id,
        nombre=data["nombre"].strip(),
        rol=(data.get("rol") or "").strip() or None,
        correo=(data.get("correo") or "").strip() or None,
        despacho=(data.get("despacho") or "").strip() or None,
        aula_virtual=(data.get("aula_virtual") or "").strip() or None,
        orden=data.get("orden", max_orden + 1),
    )
    db.session.add(profesor)
    db.session.commit()
    return jsonify(profesor.to_dict()), 201


@profesores_bp.put("/profesores/<int:profesor_id>")
def actualizar_profesor(profesor_id):
    profesor = Profesor.query.get_or_404(profesor_id)
    data = request.get_json(silent=True) or {}

    if "nombre" in data:
        if not data["nombre"]:
            raise ApiError("'nombre' no puede estar vacío")
        profesor.nombre = data["nombre"].strip()
    if "rol" in data:
        profesor.rol = (data["rol"] or "").strip() or None
    if "correo" in data:
        profesor.correo = (data["correo"] or "").strip() or None
    if "despacho" in data:
        profesor.despacho = (data["despacho"] or "").strip() or None
    if "aula_virtual" in data:
        profesor.aula_virtual = (data["aula_virtual"] or "").strip() or None
    if "orden" in data:
        profesor.orden = data["orden"]

    db.session.commit()
    return jsonify(profesor.to_dict())


@profesores_bp.delete("/profesores/<int:profesor_id>")
def borrar_profesor(profesor_id):
    profesor = Profesor.query.get_or_404(profesor_id)
    db.session.delete(profesor)
    db.session.commit()
    return "", 204
