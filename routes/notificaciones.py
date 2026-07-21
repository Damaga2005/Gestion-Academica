from datetime import date

from flask import Blueprint, jsonify

from models import Asignatura, TareaEvento
from routes.configuracion import obtener_configuracion

notificaciones_bp = Blueprint("notificaciones", __name__)

NIVEL_ORDEN = {"rojo": 0, "naranja": 1, "gris": 2}


def _ultima_actividad(asignatura):
    """Última fecha con actividad registrada en la asignatura: notas editadas o documentos subidos."""
    fechas = []
    if asignatura.notas_actualizado_en:
        fechas.append(asignatura.notas_actualizado_en.date())
    for documento in asignatura.documentos:
        fechas.append(documento.fecha_subida.date())
    return max(fechas) if fechas else None


def calcular_notificaciones():
    config = obtener_configuracion()
    hoy = date.today()
    notificaciones = []

    for tarea in TareaEvento.query.filter_by(completada=False).all():
        dias_restantes = (tarea.fecha - hoy).days
        etiqueta_tipo = tarea.tipo.replace("_", " ").capitalize()
        url = f"/vista/calendario?anio={tarea.fecha.year}&mes={tarea.fecha.month}"

        if dias_restantes < 0:
            dias_atraso = -dias_restantes
            notificaciones.append({
                "tipo": "tarea",
                "nivel": "rojo",
                "titulo": tarea.titulo,
                "mensaje": f"{etiqueta_tipo} atrasada desde hace {dias_atraso} día{'s' if dias_atraso != 1 else ''} "
                           f"({tarea.fecha.isoformat()})",
                "url": url,
            })
        elif dias_restantes <= config.dias_aviso_examen:
            nivel = "rojo" if dias_restantes < 3 else "naranja"
            cuando = "hoy" if dias_restantes == 0 else f"en {dias_restantes} día{'s' if dias_restantes != 1 else ''}"
            notificaciones.append({
                "tipo": "tarea",
                "nivel": nivel,
                "titulo": tarea.titulo,
                "mensaje": f"{etiqueta_tipo} {cuando} ({tarea.fecha.isoformat()})",
                "url": url,
            })

    # Asignaturas que se están cursando activamente, sin actividad reciente registrada.
    # (No aplica a "pendiente" en el sentido de "aún no empezada": ahí no hay nada que "abandonar" todavía.)
    for asignatura in Asignatura.query.filter_by(estado="cursando").all():
        ultima = _ultima_actividad(asignatura)
        if ultima is None:
            continue  # sin ninguna actividad previa registrada: no hay base para medir "desde cuándo"
        dias_inactivo = (hoy - ultima).days
        if dias_inactivo > config.dias_asignatura_abandonada:
            notificaciones.append({
                "tipo": "asignatura_inactiva",
                "nivel": "gris",
                "titulo": asignatura.nombre,
                "mensaje": f"Sin actividad registrada desde hace {dias_inactivo} días",
                "url": f"/vista/asignaturas/{asignatura.id}",
            })

    notificaciones.sort(key=lambda n: NIVEL_ORDEN[n["nivel"]])
    return notificaciones


@notificaciones_bp.get("/notificaciones")
def obtener_notificaciones():
    return jsonify(calcular_notificaciones())
