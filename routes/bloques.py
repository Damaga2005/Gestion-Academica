from flask import Blueprint, request, jsonify

from models import db, BloqueEvaluacion, ComponenteEvaluacion, EsquemaEvaluacion, mover_en_lista
from routes.errors import ApiError

bloques_bp = Blueprint("bloques", __name__)


@bloques_bp.post("/esquemas/<int:esquema_id>/bloques")
def crear_bloque(esquema_id):
    esquema = EsquemaEvaluacion.query.get_or_404(esquema_id)
    data = request.get_json(silent=True) or {}
    for campo in ("nombre", "porcentaje"):
        if campo not in data:
            raise ApiError(f"'{campo}' es obligatorio")

    orden = max((b.orden for b in esquema.bloques), default=-1) + 1
    bloque = BloqueEvaluacion(esquema_id=esquema.id, nombre=data["nombre"], porcentaje=data["porcentaje"], orden=orden)
    db.session.add(bloque)
    db.session.commit()
    return jsonify(bloque.to_dict()), 201


@bloques_bp.put("/bloques/<int:bloque_id>")
def actualizar_bloque(bloque_id):
    bloque = BloqueEvaluacion.query.get_or_404(bloque_id)
    data = request.get_json(silent=True) or {}
    if "nombre" in data:
        if not data["nombre"]:
            raise ApiError("'nombre' no puede estar vacío")
        bloque.nombre = data["nombre"]
    if "porcentaje" in data:
        bloque.porcentaje = data["porcentaje"]
    if "orden" in data:
        bloque.orden = data["orden"]
    db.session.commit()
    return jsonify(bloque.to_dict())


@bloques_bp.delete("/bloques/<int:bloque_id>")
def borrar_bloque(bloque_id):
    """Borra el bloque y, en cascada, sus componentes (models.py) — nunca afecta a
    otros bloques/componentes sueltos del mismo esquema."""
    bloque = BloqueEvaluacion.query.get_or_404(bloque_id)
    db.session.delete(bloque)
    db.session.commit()
    return "", 204


@bloques_bp.post("/bloques/<int:bloque_id>/componentes")
def crear_componente_en_bloque(bloque_id):
    bloque = BloqueEvaluacion.query.get_or_404(bloque_id)
    data = request.get_json(silent=True) or {}
    for campo in ("nombre", "porcentaje"):
        if campo not in data:
            raise ApiError(f"'{campo}' es obligatorio")

    componente = ComponenteEvaluacion(
        asignatura_id=bloque.esquema.asignatura_id,
        esquema_id=bloque.esquema_id,
        bloque_id=bloque.id,
        nombre=data["nombre"],
        tipo=data.get("tipo", "otro"),
        porcentaje=data["porcentaje"],
        nota=data.get("nota"),
    )
    db.session.add(componente)
    db.session.commit()
    return jsonify(componente.to_dict()), 201


def _direccion(data):
    if data.get("direccion") not in ("arriba", "abajo"):
        raise ApiError("'direccion' debe ser 'arriba' o 'abajo'")
    return data["direccion"]


@bloques_bp.post("/bloques/<int:bloque_id>/mover")
def mover_bloque(bloque_id):
    bloque = BloqueEvaluacion.query.get_or_404(bloque_id)
    mover_en_lista(bloque.esquema.bloques, bloque, _direccion(request.get_json(silent=True) or {}))
    db.session.commit()
    return "", 204


@bloques_bp.post("/componentes/<int:componente_id>/mover")
def mover_componente(componente_id):
    componente = ComponenteEvaluacion.query.get_or_404(componente_id)
    hermanos = ComponenteEvaluacion.query.filter_by(
        esquema_id=componente.esquema_id, bloque_id=componente.bloque_id
    ).order_by(ComponenteEvaluacion.orden, ComponenteEvaluacion.id).all()
    mover_en_lista(hermanos, componente, _direccion(request.get_json(silent=True) or {}))
    db.session.commit()
    return "", 204
