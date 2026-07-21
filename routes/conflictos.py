"""
Detección de conflictos de horario (spec Fase Calendario/Horario punto 7).

No es un blueprint con rutas propias por sí solo: `detectar_conflictos()` es la
lógica compartida que usan tanto `routes/tareas.py` como `routes/horarios.py` al
crear/editar un evento con hora, y `conflictos_bp` expone además un endpoint
independiente para comprobar un intervalo suelto antes de guardarlo (usado por el
formulario del frontend para avisar sin bloquear).
"""

from flask import Blueprint, request, jsonify

from models import TareaEvento, HorarioClase, intervalos_solapan, fecha_es_sesion_de_horario
from routes.errors import ApiError

conflictos_bp = Blueprint("conflictos", __name__)


def detectar_conflictos(fecha, hora_inicio, hora_fin, excluir_tarea_id=None, excluir_horario_id=None):
    """
    Devuelve la lista de eventos (tareas puntuales + sesiones de horarios
    recurrentes) que se solapan con [hora_inicio, hora_fin) el día `fecha`.

    No bloquea nada por sí misma (spec: "Permite guardar igualmente"); el llamador
    decide qué hacer con la lista (mostrarla como advertencia).
    """
    conflictos = []

    tareas_del_dia = TareaEvento.query.filter(
        TareaEvento.fecha == fecha,
        TareaEvento.hora_inicio.isnot(None),
        TareaEvento.hora_fin.isnot(None),
    )
    if excluir_tarea_id is not None:
        tareas_del_dia = tareas_del_dia.filter(TareaEvento.id != excluir_tarea_id)

    for tarea in tareas_del_dia:
        if intervalos_solapan(hora_inicio, hora_fin, tarea.hora_inicio, tarea.hora_fin):
            conflictos.append({
                "tipo": "tarea",
                "id": tarea.id,
                "titulo": tarea.titulo,
                "asignatura_siglas": tarea.asignatura.siglas if tarea.asignatura else None,
                "asignatura_nombre": tarea.asignatura.nombre if tarea.asignatura else None,
                "fecha": fecha.isoformat(),
                "hora_inicio": tarea.hora_inicio.strftime("%H:%M"),
                "hora_fin": tarea.hora_fin.strftime("%H:%M"),
            })

    horarios = HorarioClase.query
    if excluir_horario_id is not None:
        horarios = horarios.filter(HorarioClase.id != excluir_horario_id)

    for horario in horarios:
        if not fecha_es_sesion_de_horario(fecha, horario):
            continue
        if intervalos_solapan(hora_inicio, hora_fin, horario.hora_inicio, horario.hora_fin):
            conflictos.append({
                "tipo": "horario",
                "id": horario.id,
                "titulo": f"{horario.tipo.capitalize()} de {horario.asignatura.nombre}",
                "asignatura_siglas": horario.asignatura.siglas,
                "asignatura_nombre": horario.asignatura.nombre,
                "fecha": fecha.isoformat(),
                "hora_inicio": horario.hora_inicio.strftime("%H:%M"),
                "hora_fin": horario.hora_fin.strftime("%H:%M"),
                "aula": horario.aula,
            })

    return conflictos


@conflictos_bp.post("/calendario/comprobar-conflictos")
def comprobar_conflictos_ruta():
    """
    Comprobación bajo demanda antes de guardar (formulario de crear tarea/horario):
    body { "fecha": "YYYY-MM-DD", "hora_inicio": "HH:MM", "hora_fin": "HH:MM" }.
    """
    from datetime import datetime

    data = request.get_json(silent=True) or {}
    for campo in ("fecha", "hora_inicio", "hora_fin"):
        if not data.get(campo):
            raise ApiError(f"'{campo}' es obligatorio")

    try:
        fecha = datetime.strptime(data["fecha"], "%Y-%m-%d").date()
        hora_inicio = datetime.strptime(data["hora_inicio"], "%H:%M").time()
        hora_fin = datetime.strptime(data["hora_fin"], "%H:%M").time()
    except ValueError:
        raise ApiError("formato de fecha/hora inválido (fecha: YYYY-MM-DD, horas: HH:MM)")

    conflictos = detectar_conflictos(
        fecha, hora_inicio, hora_fin,
        excluir_tarea_id=data.get("excluir_tarea_id"),
        excluir_horario_id=data.get("excluir_horario_id"),
    )
    return jsonify({"conflictos": conflictos})
