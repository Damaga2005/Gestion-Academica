from flask import Blueprint, request, jsonify

from models import db, ComponenteEvaluacion, Asignatura, EsquemaEvaluacion
from routes.errors import ApiError

componentes_bp = Blueprint("componentes", __name__)


@componentes_bp.get("/asignaturas/<int:asignatura_id>/componentes")
def listar_componentes(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    componentes = ComponenteEvaluacion.query.filter_by(asignatura_id=asignatura_id).all()
    return jsonify([c.to_dict() for c in componentes])


@componentes_bp.post("/asignaturas/<int:asignatura_id>/componentes")
def crear_componente(asignatura_id):
    """
    Ruta histórica (anterior a los esquemas de evaluación múltiples), que se mantiene
    para no romper nada: sigue funcionando igual cuando la asignatura tiene 0 o 1
    esquema (el caso normal), creando uno "Evaluación" sobre la marcha si aún no
    existe ninguno. Si ya hay más de un esquema, la ambigüedad de a cuál pertenece el
    componente nuevo no se puede resolver aquí: hay que usar
    POST /esquemas/<esquema_id>/componentes.
    """
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}
    for campo in ("nombre", "porcentaje"):
        if campo not in data:
            raise ApiError(f"'{campo}' es obligatorio")

    esquemas = asignatura.esquemas
    if len(esquemas) == 0:
        esquema = EsquemaEvaluacion(asignatura_id=asignatura_id, nombre="Evaluación", orden=0)
        db.session.add(esquema)
        db.session.flush()
    elif len(esquemas) == 1:
        esquema = esquemas[0]
    else:
        raise ApiError(
            "esta asignatura tiene varios esquemas de evaluación: indica a cuál añadir "
            "el componente con POST /esquemas/<esquema_id>/componentes",
            422,
        )

    componente = ComponenteEvaluacion(
        asignatura_id=asignatura_id,
        esquema_id=esquema.id,
        nombre=data["nombre"],
        tipo=data.get("tipo", "otro"),
        porcentaje=data["porcentaje"],
        nota=data.get("nota"),
    )
    db.session.add(componente)
    db.session.commit()
    return jsonify(componente.to_dict()), 201


@componentes_bp.get("/componentes/<int:componente_id>")
def obtener_componente(componente_id):
    componente = ComponenteEvaluacion.query.get_or_404(componente_id)
    return jsonify(componente.to_dict())


@componentes_bp.put("/componentes/<int:componente_id>")
def actualizar_componente(componente_id):
    componente = ComponenteEvaluacion.query.get_or_404(componente_id)
    data = request.get_json(silent=True) or {}

    if "nombre" in data:
        if not str(data["nombre"] or "").strip():
            raise ApiError("'nombre' no puede estar vacío")
        componente.nombre = data["nombre"]
    if "tipo" in data:
        componente.tipo = data["tipo"]
    if "porcentaje" in data:
        if not isinstance(data["porcentaje"], (int, float)) or not 0 <= data["porcentaje"] <= 100:
            raise ApiError("'porcentaje' debe estar entre 0 y 100")
        componente.porcentaje = data["porcentaje"]
    if "nota_minima" in data:
        v = data["nota_minima"]
        if v is not None and (not isinstance(v, (int, float)) or not 0 <= v <= 10):
            raise ApiError("'nota_minima' debe estar entre 0 y 10")
        componente.nota_minima = v
    if "nota" in data:
        componente.nota = data["nota"]
    if "bloque_id" in data:
        componente.bloque_id = data["bloque_id"]

    db.session.commit()
    return jsonify(componente.to_dict())


@componentes_bp.delete("/componentes/<int:componente_id>")
def borrar_componente(componente_id):
    componente = ComponenteEvaluacion.query.get_or_404(componente_id)
    db.session.delete(componente)
    db.session.commit()
    return "", 204
