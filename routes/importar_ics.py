"""Importar tareas desde un .ics (p. ej. el calendario exportado de Atenea/Moodle).

Dos pasos, como la guía docente: /analizar solo lee y propone (nunca escribe), y
/importar escribe únicamente lo que el usuario dejó marcado en la previsualización.
"""

import re
import unicodedata
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

from flask import Blueprint, jsonify, request

from models import db, Asignatura, TareaEvento, TIPOS_TAREA
from routes.errors import ApiError
from routes.tareas import _parse_fecha, _parse_hora

importar_ics_bp = Blueprint("importar_ics", __name__)

_MAX_BYTES = 2 * 1024 * 1024


def _desescapar(valor):
    return re.sub(r"\\([,;nN\\])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), valor)


def _leer_eventos(texto):
    """Devuelve una lista de dicts {NOMBRE_PROPIEDAD: (params, valor)} por VEVENT."""
    lineas = []
    for linea in texto.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if linea[:1] in (" ", "\t") and lineas:
            lineas[-1] += linea[1:]  # línea plegada (RFC 5545)
        else:
            lineas.append(linea)

    eventos, actual = [], None
    for linea in lineas:
        if linea == "BEGIN:VEVENT":
            actual = {}
        elif linea == "END:VEVENT":
            if actual is not None:
                eventos.append(actual)
            actual = None
        elif actual is not None and ":" in linea:
            cabecera, valor = linea.split(":", 1)
            nombre, _, params = cabecera.partition(";")
            actual.setdefault(nombre.upper(), (params.upper(), _desescapar(valor)))
    return eventos


def _ultimo_domingo(anio, mes):
    d = date(anio, mes + 1, 1) - timedelta(days=1) if mes < 12 else date(anio, 12, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _utc_a_madrid(dt):
    """Hora peninsular sin depender de tzdata (que en Windows/PyInstaller no viene):
    UTC+2 entre el último domingo de marzo y el de octubre (01:00 UTC), UTC+1 el resto."""
    inicio = datetime.combine(_ultimo_domingo(dt.year, 3), datetime.min.time()) + timedelta(hours=1)
    fin = datetime.combine(_ultimo_domingo(dt.year, 10), datetime.min.time()) + timedelta(hours=1)
    return dt + timedelta(hours=2 if inicio <= dt < fin else 1)


def _fecha_hora(params, valor):
    """(date, "HH:MM" | None) de un DTSTART. Sin hora si es de día completo."""
    valor = valor.strip()
    if "VALUE=DATE" in params or re.fullmatch(r"\d{8}", valor):
        return datetime.strptime(valor[:8], "%Y%m%d").date(), None
    dt = datetime.strptime(valor.rstrip("Z"), "%Y%m%dT%H%M%S")
    if valor.endswith("Z"):
        dt = _utc_a_madrid(dt)
    return dt.date(), dt.strftime("%H:%M")


def _normaliza(texto):
    t = unicodedata.normalize("NFD", texto or "")
    return re.sub(r"[^a-z0-9 ]", "", "".join(c for c in t if not unicodedata.combining(c)).lower()).strip()


def _adivinar_asignatura(curso, asignaturas):
    """Mejor asignatura por parecido del nombre del curso (quitando el código inicial y
    "(Curs N)"). Los nombres en catalán y castellano se parecen lo bastante; si no llega
    al umbral no se sugiere nada y lo elige el usuario."""
    limpio = _normaliza(re.sub(r"\(.*?\)|^\s*\d{4,}\s*-?", "", curso))
    mejor, ratio_mejor = None, 0.0
    for a in asignaturas:
        ratio = SequenceMatcher(None, limpio, _normaliza(a.nombre)).ratio()
        if ratio > ratio_mejor:
            mejor, ratio_mejor = a, ratio
    return mejor.id if mejor and ratio_mejor >= 0.6 else None


def _tipo(url, titulo, descripcion):
    if "/mod/quiz/" in url:
        return "tarea_general"
    if "/mod/assign/" in url:
        return "entrega"
    texto = _normaliza(f"{titulo} {descripcion}")
    return "entrega" if re.search(r"entrega|lliurament|tasca|assign", texto) else "tarea_general"


def _ya_existe(titulo, fecha):
    return db.session.query(TareaEvento.id).filter(
        db.func.lower(TareaEvento.titulo) == titulo.strip().lower(), TareaEvento.fecha == fecha
    ).first() is not None


@importar_ics_bp.post("/calendario/importar-ics/analizar")
def analizar():
    archivo = request.files.get("archivo")
    if archivo is None:
        raise ApiError("falta el archivo .ics")
    crudo = archivo.read(_MAX_BYTES + 1)
    if len(crudo) > _MAX_BYTES:
        raise ApiError("el archivo .ics es demasiado grande")
    texto = crudo.decode("utf-8-sig", errors="replace")
    if "BEGIN:VCALENDAR" not in texto:
        raise ApiError("no parece un archivo .ics válido")

    asignaturas = Asignatura.query.filter(Asignatura.estado != "no_elegida").order_by(Asignatura.nombre).all()
    propuesta = []
    for ev in _leer_eventos(texto):
        if "SUMMARY" not in ev or "DTSTART" not in ev:
            continue
        titulo = ev["SUMMARY"][1].strip()
        try:
            fecha, hora = _fecha_hora(*ev["DTSTART"])
        except ValueError:
            continue
        curso = ev.get("CATEGORIES", ("", ""))[1].split(",")[0].strip()
        descripcion = ev.get("DESCRIPTION", ("", ""))[1]
        propuesta.append({
            "titulo": titulo,
            "fecha": fecha.isoformat(),
            "hora_fin": hora,
            "tipo": _tipo(ev.get("URL", ("", ""))[1], titulo, descripcion),
            "curso": curso,
            "asignatura_id": _adivinar_asignatura(curso, asignaturas),
            "duplicado": _ya_existe(titulo, fecha),
        })
    propuesta.sort(key=lambda e: (e["fecha"], e["hora_fin"] or ""))
    return jsonify({
        "eventos": propuesta,
        "asignaturas": [{"id": a.id, "siglas": a.siglas, "nombre": a.nombre} for a in asignaturas],
    })


@importar_ics_bp.post("/calendario/importar-ics")
def importar():
    data = request.get_json(silent=True) or {}
    eventos = data.get("eventos")
    if not isinstance(eventos, list):
        raise ApiError("'eventos' debe ser una lista")

    creadas = omitidas = 0
    for ev in eventos:
        titulo = (ev.get("titulo") or "").strip()
        if not titulo:
            raise ApiError("cada evento necesita un título")
        fecha = _parse_fecha(ev.get("fecha"))
        if ev.get("tipo", "tarea_general") not in TIPOS_TAREA:
            raise ApiError(f"tipo debe ser uno de {TIPOS_TAREA}")
        asignatura_id = ev.get("asignatura_id")
        if asignatura_id is not None and db.session.get(Asignatura, asignatura_id) is None:
            raise ApiError("asignatura no encontrada")
        if _ya_existe(titulo, fecha):
            omitidas += 1
            continue
        db.session.add(TareaEvento(
            asignatura_id=asignatura_id, titulo=titulo, fecha=fecha,
            tipo=ev.get("tipo", "tarea_general"), hora_fin=_parse_hora(ev.get("hora_fin"), "hora_fin"),
        ))
        creadas += 1
    db.session.commit()
    return jsonify({"creadas": creadas, "omitidas": omitidas}), 201
