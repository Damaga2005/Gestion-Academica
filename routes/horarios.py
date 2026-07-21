from datetime import datetime

from flask import Blueprint, request, jsonify

from models import (
    db, HorarioClase, TIPOS_HORARIO, DIAS_SEMANA, INTERVALOS_SEMANAS,
    fechas_sesiones_horario, resolver_asignatura,
)
from routes.errors import ApiError
from routes.conflictos import detectar_conflictos

horarios_bp = Blueprint("horarios", __name__)


def _parse_fecha(valor, campo):
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ApiError(f"'{campo}' debe tener formato YYYY-MM-DD")


def _parse_hora(valor, campo):
    try:
        return datetime.strptime(valor, "%H:%M").time()
    except (ValueError, TypeError):
        raise ApiError(f"'{campo}' debe tener formato HH:MM")


def _conflictos_de_serie(horario, excluir_horario_id=None):
    """Agrega los conflictos de TODAS las sesiones de la serie (no solo la
    primera), pero sin duplicar el mismo evento conflictivo varias veces en la
    respuesta si coincide en más de una sesión (p. ej. un examen que choca con
    una clase que se repite toda la asignatura)."""
    vistos = set()
    agregados = []
    for fecha in fechas_sesiones_horario(horario):
        for conflicto in detectar_conflictos(
            fecha, horario.hora_inicio, horario.hora_fin, excluir_horario_id=excluir_horario_id
        ):
            clave = (conflicto["tipo"], conflicto["id"], conflicto["fecha"])
            if clave in vistos:
                continue
            vistos.add(clave)
            agregados.append(conflicto)
    return agregados


def _validar_y_construir_datos(data, parcial=False):
    """Valida y normaliza el body de creación/edición. `parcial=True` (PUT) solo
    exige los campos que vienen en el body; `parcial=False` (POST) los exige todos."""
    campos_obligatorios = (
        "asignatura_id", "tipo", "dia_semana", "hora_inicio", "hora_fin",
        "fecha_inicio", "fecha_fin",
    )
    if not parcial:
        for campo in campos_obligatorios:
            if campo not in data:
                raise ApiError(f"'{campo}' es obligatorio")

    resultado = {}

    if "asignatura_id" in data:
        asignatura = resolver_asignatura(data["asignatura_id"])
        if asignatura is None:
            raise ApiError(f"no existe ninguna asignatura con id/siglas '{data['asignatura_id']}'", 404)
        resultado["asignatura_id"] = asignatura.id

    if "tipo" in data:
        if data["tipo"] not in TIPOS_HORARIO:
            raise ApiError(f"tipo debe ser uno de {TIPOS_HORARIO}", 422)
        resultado["tipo"] = data["tipo"]

    if "dia_semana" in data:
        if data["dia_semana"] not in DIAS_SEMANA:
            raise ApiError(f"dia_semana debe ser uno de {DIAS_SEMANA} (1=lunes...5=viernes)", 422)
        resultado["dia_semana"] = data["dia_semana"]

    if "hora_inicio" in data:
        resultado["hora_inicio"] = _parse_hora(data["hora_inicio"], "hora_inicio")
    if "hora_fin" in data:
        resultado["hora_fin"] = _parse_hora(data["hora_fin"], "hora_fin")

    if "fecha_inicio" in data:
        resultado["fecha_inicio"] = _parse_fecha(data["fecha_inicio"], "fecha_inicio")
    if "fecha_fin" in data:
        resultado["fecha_fin"] = _parse_fecha(data["fecha_fin"], "fecha_fin")

    if "intervalo_semanas" in data:
        if data["intervalo_semanas"] not in INTERVALOS_SEMANAS:
            raise ApiError(f"intervalo_semanas debe ser uno de {INTERVALOS_SEMANAS}", 422)
        resultado["intervalo_semanas"] = data["intervalo_semanas"]

    if "aula" in data:
        resultado["aula"] = data["aula"]
    if "notas" in data:
        resultado["notas"] = data["notas"]

    return resultado


def _validar_coherencia(horario):
    if horario.hora_fin <= horario.hora_inicio:
        raise ApiError("'hora_fin' debe ser posterior a 'hora_inicio'")
    if horario.fecha_fin < horario.fecha_inicio:
        raise ApiError("'fecha_fin' debe ser posterior o igual a 'fecha_inicio'")


@horarios_bp.get("/horarios")
def listar_horarios():
    query = HorarioClase.query
    asignatura_id = request.args.get("asignatura_id")
    dia_semana = request.args.get("dia_semana", type=int)
    tipo = request.args.get("tipo")

    if asignatura_id is not None:
        asignatura = resolver_asignatura(asignatura_id)
        query = query.filter_by(asignatura_id=asignatura.id if asignatura else -1)
    if dia_semana is not None:
        query = query.filter_by(dia_semana=dia_semana)
    if tipo is not None:
        query = query.filter_by(tipo=tipo)

    horarios = query.order_by(HorarioClase.dia_semana, HorarioClase.hora_inicio).all()
    return jsonify([h.to_dict() for h in horarios])


@horarios_bp.get("/horarios/<int:horario_id>")
def obtener_horario(horario_id):
    horario = HorarioClase.query.get_or_404(horario_id)
    return jsonify(horario.to_dict())


@horarios_bp.get("/horarios/<int:horario_id>/sesiones")
def sesiones_horario(horario_id):
    """Fechas concretas (ISO) de cada sesión de la serie, calculadas al vuelo."""
    horario = HorarioClase.query.get_or_404(horario_id)
    return jsonify([f.isoformat() for f in fechas_sesiones_horario(horario)])


@horarios_bp.post("/horarios")
def crear_horario():
    data = request.get_json(silent=True) or {}
    campos = _validar_y_construir_datos(data, parcial=False)

    horario = HorarioClase(
        asignatura_id=campos["asignatura_id"],
        tipo=campos["tipo"],
        dia_semana=campos["dia_semana"],
        hora_inicio=campos["hora_inicio"],
        hora_fin=campos["hora_fin"],
        fecha_inicio=campos["fecha_inicio"],
        fecha_fin=campos["fecha_fin"],
        intervalo_semanas=campos.get("intervalo_semanas", 1),
        aula=campos.get("aula"),
        notas=campos.get("notas"),
    )
    _validar_coherencia(horario)

    conflictos = _conflictos_de_serie(horario)

    db.session.add(horario)
    db.session.commit()

    respuesta = horario.to_dict()
    respuesta["conflictos"] = conflictos
    return jsonify(respuesta), 201


@horarios_bp.put("/horarios/<int:horario_id>")
def actualizar_horario(horario_id):
    """Editar la serie completa (spec punto 6: no hay excepciones por sesión, los
    cambios se aplican a todas las sesiones de golpe porque solo existe una fila)."""
    horario = HorarioClase.query.get_or_404(horario_id)
    data = request.get_json(silent=True) or {}
    campos = _validar_y_construir_datos(data, parcial=True)

    for clave, valor in campos.items():
        setattr(horario, clave, valor)
    _validar_coherencia(horario)

    conflictos = _conflictos_de_serie(horario, excluir_horario_id=horario.id)

    db.session.commit()

    respuesta = horario.to_dict()
    respuesta["conflictos"] = conflictos
    return jsonify(respuesta)


@horarios_bp.delete("/horarios/<int:horario_id>")
def borrar_horario(horario_id):
    """Elimina toda la serie (spec punto 6: no se implementan excepciones de una
    sola sesión). La confirmación explícita ("se eliminarán todas las sesiones de
    esta serie") es responsabilidad del cliente antes de llamar a esta ruta."""
    horario = HorarioClase.query.get_or_404(horario_id)
    db.session.delete(horario)
    db.session.commit()
    return "", 204
