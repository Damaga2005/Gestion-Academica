"""
Exportación a iCalendar (.ics) — spec Fase Calendario/Horario punto 8.

Construido a mano (sin librería `icalendar`, para no añadir una dependencia nueva
solo para esto) siguiendo RFC 5545 en lo esencial: VEVENT con DTSTART/DTEND en
hora local "flotante" (sin TZID) para eventos puntuales, y RRULE semanal/quincenal
con BYDAY para las series de horario recurrente.

Preparado para integraciones futuras (spec: "prepara la arquitectura para futuras
integraciones con Google Calendar, Apple Calendar y Outlook. No implementes OAuth
ni sincronización bidireccional en esta fase"): cada evento lleva un UID estable
(prefijo + id interno), que es el enganche que necesitaría una sincronización
bidireccional futura para saber qué evento local corresponde a cuál remoto, sin
tener que rediseñar el formato de exportación cuando llegue esa fase.
"""

from datetime import datetime, timedelta

from flask import Blueprint, Response

from models import TareaEvento, HorarioClase, fechas_sesiones_horario

ics_bp = Blueprint("ics", __name__)

BYDAY_POR_DIA_SEMANA = {1: "MO", 2: "TU", 3: "WE", 4: "TH", 5: "FR"}

ETIQUETA_TIPO_HORARIO = {
    "teoria": "Teoría", "problemas": "Problemas", "laboratorio": "Laboratorio", "seminario": "Seminario",
}


def _escapar_ics(texto):
    if not texto:
        return ""
    return (
        str(texto)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _dtstamp_ahora():
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _vevent_tarea(tarea):
    """Un examen o evento puntual. Con hora: DTSTART/DTEND datetime local flotante.
    Sin hora: evento de día completo (DTEND exclusivo, un día después, per RFC5545)."""
    lineas = ["BEGIN:VEVENT", f"UID:tarea-{tarea.id}@greelec.local", f"DTSTAMP:{_dtstamp_ahora()}"]

    if tarea.hora_inicio and tarea.hora_fin:
        fecha_str = tarea.fecha.strftime("%Y%m%d")
        lineas.append(f"DTSTART:{fecha_str}T{tarea.hora_inicio.strftime('%H%M%S')}")
        lineas.append(f"DTEND:{fecha_str}T{tarea.hora_fin.strftime('%H%M%S')}")
    else:
        lineas.append(f"DTSTART;VALUE=DATE:{tarea.fecha.strftime('%Y%m%d')}")
        lineas.append(f"DTEND;VALUE=DATE:{(tarea.fecha + timedelta(days=1)).strftime('%Y%m%d')}")

    resumen = tarea.titulo
    if tarea.asignatura:
        prefijo = tarea.asignatura.siglas or tarea.asignatura.nombre
        resumen = f"{prefijo} · {tarea.titulo}"
    lineas.append(f"SUMMARY:{_escapar_ics(resumen)}")

    if tarea.aula or tarea.ubicacion:
        lugar = " · ".join(p for p in (tarea.aula, tarea.ubicacion) if p)
        lineas.append(f"LOCATION:{_escapar_ics(lugar)}")
    if tarea.descripcion:
        lineas.append(f"DESCRIPTION:{_escapar_ics(tarea.descripcion)}")

    lineas.append("END:VEVENT")
    return lineas


def _vevent_horario(horario):
    """Una serie recurrente completa como UN VEVENT con RRULE (no un VEVENT por
    sesión): DTSTART = primera sesión calculada, RRULE repite semanal/quincenal
    hasta fecha_fin."""
    sesiones = fechas_sesiones_horario(horario)
    if not sesiones:
        return []
    primera = sesiones[0]

    lineas = ["BEGIN:VEVENT", f"UID:horario-{horario.id}@greelec.local", f"DTSTAMP:{_dtstamp_ahora()}"]
    lineas.append(f"DTSTART:{primera.strftime('%Y%m%d')}T{horario.hora_inicio.strftime('%H%M%S')}")
    lineas.append(f"DTEND:{primera.strftime('%Y%m%d')}T{horario.hora_fin.strftime('%H%M%S')}")

    hasta = horario.fecha_fin.strftime("%Y%m%d") + "T235959Z"
    byday = BYDAY_POR_DIA_SEMANA[horario.dia_semana]
    lineas.append(f"RRULE:FREQ=WEEKLY;INTERVAL={horario.intervalo_semanas};BYDAY={byday};UNTIL={hasta}")

    prefijo = horario.asignatura.siglas or horario.asignatura.nombre
    resumen = f"{prefijo} · {ETIQUETA_TIPO_HORARIO.get(horario.tipo, horario.tipo)}"
    lineas.append(f"SUMMARY:{_escapar_ics(resumen)}")
    if horario.aula:
        lineas.append(f"LOCATION:{_escapar_ics(horario.aula)}")
    if horario.notas:
        lineas.append(f"DESCRIPTION:{_escapar_ics(horario.notas)}")

    lineas.append("END:VEVENT")
    return lineas


def _construir_calendario(lineas_vevents):
    return "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//GREELEC//Gestion Academica//ES",
        "CALSCALE:GREGORIAN",
        *lineas_vevents,
        "END:VCALENDAR",
        "",
    ])


def _respuesta_ics(contenido, nombre_archivo):
    return Response(
        contenido,
        mimetype="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@ics_bp.get("/tareas/<int:tarea_id>/ics")
def exportar_tarea_ics(tarea_id):
    tarea = TareaEvento.query.get_or_404(tarea_id)
    contenido = _construir_calendario(_vevent_tarea(tarea))
    return _respuesta_ics(contenido, f"evento_{tarea_id}.ics")


@ics_bp.get("/horarios/<int:horario_id>/ics")
def exportar_horario_ics(horario_id):
    horario = HorarioClase.query.get_or_404(horario_id)
    contenido = _construir_calendario(_vevent_horario(horario))
    return _respuesta_ics(contenido, f"horario_{horario_id}.ics")


@ics_bp.get("/horarios/ics")
def exportar_todo_el_horario_ics():
    """Todas las series de horario recurrente (sin las tareas del calendario
    académico) — "todo el horario" de la spec, como pieza separada de "todo el
    calendario"."""
    lineas = []
    for horario in HorarioClase.query.all():
        lineas.extend(_vevent_horario(horario))
    contenido = _construir_calendario(lineas)
    return _respuesta_ics(contenido, "horario_completo.ics")


@ics_bp.get("/calendario/ics")
def exportar_calendario_completo_ics():
    """Todo: todas las tareas/eventos del calendario académico + todas las series
    de horario recurrente, en un único archivo ("todo el horario" + calendario)."""
    lineas = []
    for tarea in TareaEvento.query.order_by(TareaEvento.fecha).all():
        lineas.extend(_vevent_tarea(tarea))
    for horario in HorarioClase.query.all():
        lineas.extend(_vevent_horario(horario))
    contenido = _construir_calendario(lineas)
    return _respuesta_ics(contenido, "calendario_greelec.ics")
