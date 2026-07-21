from flask import Blueprint, request, jsonify

from models import db, Asignatura, EsquemaEvaluacion, ComponenteEvaluacion, esquemas_con_ganador, REGLAS_ESQUEMA
from routes.errors import ApiError

esquemas_bp = Blueprint("esquemas", __name__)


@esquemas_bp.get("/asignaturas/<int:asignatura_id>/esquemas")
def listar_esquemas(asignatura_id):
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    return jsonify(esquemas_con_ganador(asignatura.esquemas, asignatura.regla_esquemas))


@esquemas_bp.post("/asignaturas/<int:asignatura_id>/esquemas")
def crear_esquema(asignatura_id):
    """
    Crea un esquema de evaluación alternativo adicional (spec: comparación de fórmulas
    de evaluación). Body: { "nombre": "Fórmula alternativa" }.
    """
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}
    if not data.get("nombre"):
        raise ApiError("'nombre' es obligatorio")

    orden = max((e.orden for e in asignatura.esquemas), default=-1) + 1
    esquema = EsquemaEvaluacion(asignatura_id=asignatura_id, nombre=data["nombre"], orden=orden)
    db.session.add(esquema)
    db.session.commit()
    return jsonify(esquema.to_dict()), 201


@esquemas_bp.put("/esquemas/<int:esquema_id>")
def actualizar_esquema(esquema_id):
    esquema = EsquemaEvaluacion.query.get_or_404(esquema_id)
    data = request.get_json(silent=True) or {}
    if "nombre" in data:
        if not data["nombre"]:
            raise ApiError("'nombre' no puede estar vacío")
        esquema.nombre = data["nombre"]
    if "orden" in data:
        esquema.orden = data["orden"]
    db.session.commit()
    return jsonify(esquema.to_dict())


@esquemas_bp.delete("/esquemas/<int:esquema_id>")
def borrar_esquema(esquema_id):
    """
    No permite borrar el último esquema de una asignatura: toda asignatura con
    componentes de evaluación debe conservar al menos un esquema al que pertenezcan
    (el caso normal de "un único esquema" no debe poder quedarse sin ninguno).
    """
    esquema = EsquemaEvaluacion.query.get_or_404(esquema_id)
    total_esquemas = EsquemaEvaluacion.query.filter_by(asignatura_id=esquema.asignatura_id).count()
    if total_esquemas <= 1:
        raise ApiError("no se puede eliminar el único esquema de evaluación de la asignatura")
    db.session.delete(esquema)
    db.session.commit()
    return "", 204


@esquemas_bp.put("/asignaturas/<int:asignatura_id>/regla-esquemas")
def actualizar_regla_esquemas(asignatura_id):
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}
    if data.get("regla_esquemas") not in REGLAS_ESQUEMA:
        raise ApiError(f"regla_esquemas debe ser una de {REGLAS_ESQUEMA}")
    asignatura.regla_esquemas = data["regla_esquemas"]
    db.session.commit()
    return jsonify(asignatura.to_dict())


@esquemas_bp.post("/esquemas/<int:esquema_id>/componentes")
def crear_componente_en_esquema(esquema_id):
    esquema = EsquemaEvaluacion.query.get_or_404(esquema_id)
    data = request.get_json(silent=True) or {}
    for campo in ("nombre", "porcentaje"):
        if campo not in data:
            raise ApiError(f"'{campo}' es obligatorio")

    componente = ComponenteEvaluacion(
        asignatura_id=esquema.asignatura_id,
        esquema_id=esquema.id,
        nombre=data["nombre"],
        tipo=data.get("tipo", "otro"),
        porcentaje=data["porcentaje"],
        nota=data.get("nota"),
    )
    db.session.add(componente)
    db.session.commit()
    return jsonify(componente.to_dict()), 201
