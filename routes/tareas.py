import calendar as calendar_module
from datetime import date, datetime, time

from flask import Blueprint, request, jsonify

from models import db, TareaEvento, Asignatura, resolver_asignatura
from routes.errors import ApiError
from routes.conflictos import detectar_conflictos

tareas_bp = Blueprint("tareas", __name__)


def _parse_fecha(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ApiError("'fecha' debe tener formato YYYY-MM-DD")


def _parse_hora(valor, campo):
    if valor is None or valor == "":
        return None
    if isinstance(valor, time):
        return valor
    try:
        return datetime.strptime(valor, "%H:%M").time()
    except (ValueError, TypeError):
        raise ApiError(f"'{campo}' debe tener formato HH:MM")


def _parse_bool(valor):
    return str(valor).lower() in ("1", "true", "si", "sí")


def _resolver_asignatura_opcional(data, campo="asignatura_id"):
    """El campo acepta indistintamente el id numérico o las siglas (spec punto 1):
    resuelve a la Asignatura real o lanza 404 si no existe ninguna con ese valor."""
    valor = data.get(campo)
    if valor is None:
        return None
    asignatura = resolver_asignatura(valor)
    if asignatura is None:
        raise ApiError(f"no existe ninguna asignatura con id/siglas '{valor}'", 404)
    return asignatura


@tareas_bp.get("/tareas")
def listar_tareas():
    query = TareaEvento.query

    asignatura_id = request.args.get("asignatura_id")
    tipo = request.args.get("tipo")
    completada = request.args.get("completada")
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)

    if asignatura_id is not None:
        asignatura = resolver_asignatura(asignatura_id)
        query = query.filter_by(asignatura_id=asignatura.id if asignatura else -1)
    if tipo is not None:
        query = query.filter_by(tipo=tipo)
    if completada is not None:
        query = query.filter_by(completada=_parse_bool(completada))
    if anio is not None and mes is not None:
        primer_dia = date(anio, mes, 1)
        ultimo_dia = date(anio, mes, calendar_module.monthrange(anio, mes)[1])
        query = query.filter(TareaEvento.fecha >= primer_dia, TareaEvento.fecha <= ultimo_dia)

    tareas = query.order_by(TareaEvento.fecha).all()
    return jsonify([t.to_dict() for t in tareas])


@tareas_bp.get("/tareas/<int:tarea_id>")
def obtener_tarea(tarea_id):
    tarea = TareaEvento.query.get_or_404(tarea_id)
    return jsonify(tarea.to_dict())


@tareas_bp.post("/tareas")
def crear_tarea():
    data = request.get_json(silent=True) or {}
    for campo in ("titulo", "fecha"):
        if campo not in data:
            raise ApiError(f"'{campo}' es obligatorio")

    asignatura = _resolver_asignatura_opcional(data)
    hora_inicio = _parse_hora(data.get("hora_inicio"), "hora_inicio")
    hora_fin = _parse_hora(data.get("hora_fin"), "hora_fin")
    if hora_inicio and hora_fin and hora_fin <= hora_inicio:
        raise ApiError("'hora_fin' debe ser posterior a 'hora_inicio'")

    tarea = TareaEvento(
        asignatura_id=asignatura.id if asignatura else None,
        titulo=data["titulo"],
        fecha=_parse_fecha(data["fecha"]),
        tipo=data.get("tipo", "tarea_general"),
        completada=data.get("completada", False),
        prioridad=data.get("prioridad", "media"),
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        aula=data.get("aula"),
        ubicacion=data.get("ubicacion"),
        descripcion=data.get("descripcion"),
        recordatorio=data.get("recordatorio"),
        link_relacionado=data.get("link_relacionado"),
    )
    db.session.add(tarea)
    db.session.commit()

    respuesta = tarea.to_dict()
    if hora_inicio and hora_fin:
        respuesta["conflictos"] = detectar_conflictos(
            tarea.fecha, hora_inicio, hora_fin, excluir_tarea_id=tarea.id
        )
    return jsonify(respuesta), 201


@tareas_bp.put("/tareas/<int:tarea_id>")
def actualizar_tarea(tarea_id):
    tarea = TareaEvento.query.get_or_404(tarea_id)
    data = request.get_json(silent=True) or {}

    if "asignatura_id" in data:
        asignatura = _resolver_asignatura_opcional(data)
        tarea.asignatura_id = asignatura.id if asignatura else None
    if "titulo" in data:
        tarea.titulo = data["titulo"]
    if "fecha" in data:
        tarea.fecha = _parse_fecha(data["fecha"])
    if "tipo" in data:
        tarea.tipo = data["tipo"]
    if "completada" in data:
        tarea.completada = data["completada"]
    if "prioridad" in data:
        tarea.prioridad = data["prioridad"]
    if "hora_inicio" in data:
        tarea.hora_inicio = _parse_hora(data["hora_inicio"], "hora_inicio")
    if "hora_fin" in data:
        tarea.hora_fin = _parse_hora(data["hora_fin"], "hora_fin")
    if tarea.hora_inicio and tarea.hora_fin and tarea.hora_fin <= tarea.hora_inicio:
        raise ApiError("'hora_fin' debe ser posterior a 'hora_inicio'")
    if "aula" in data:
        tarea.aula = data["aula"]
    if "ubicacion" in data:
        tarea.ubicacion = data["ubicacion"]
    if "descripcion" in data:
        tarea.descripcion = data["descripcion"]
    if "recordatorio" in data:
        tarea.recordatorio = data["recordatorio"]
    if "link_relacionado" in data:
        tarea.link_relacionado = data["link_relacionado"]

    db.session.commit()
    return jsonify(tarea.to_dict())


@tareas_bp.delete("/tareas/<int:tarea_id>")
def borrar_tarea(tarea_id):
    tarea = TareaEvento.query.get_or_404(tarea_id)
    db.session.delete(tarea)
    db.session.commit()
    return "", 204


@tareas_bp.get("/tareas/calendario/<int:anio>/<int:mes>")
def calendario_mensual(anio, mes):
    """Tareas/eventos de un mes concreto, agrupadas por día (YYYY-MM-DD) para pintar la vista mensual."""
    if not (1 <= mes <= 12):
        raise ApiError("mes debe estar entre 1 y 12")

    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar_module.monthrange(anio, mes)[1])
    tareas = TareaEvento.query.filter(
        TareaEvento.fecha >= primer_dia, TareaEvento.fecha <= ultimo_dia
    ).order_by(TareaEvento.fecha).all()

    dias = {}
    for tarea in tareas:
        dias.setdefault(tarea.fecha.isoformat(), []).append(tarea.to_dict())

    return jsonify({"anio": anio, "mes": mes, "dias": dias})
