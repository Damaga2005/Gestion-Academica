"""API de anotaciones sobre el texto de un PDF (resaltar / subrayar / tachar / nota).

La geometría llega ya normalizada desde el visor (rectángulos 0..1 relativos a la
página), así que aquí solo se valida el formato y se guarda; ver AnotacionPdf.
"""

import json

from flask import Blueprint, request, jsonify

from models import db, AnotacionPdf, Documento, TIPOS_ANOTACION_PDF
from routes.errors import ApiError

anotaciones_bp = Blueprint("anotaciones", __name__)

# Paleta fija, la misma que ofrece el visor. Se valida en servidor para que el
# color acabe siempre en un valor conocido y no en CSS arbitrario venido del
# cliente, que se inyecta luego en un style del DOM.
COLORES_ANOTACION = {
    "#ffd400",  # amarillo
    "#4ade80",  # verde
    "#60a5fa",  # azul
    "#f472b6",  # rosa
    "#fb923c",  # naranja
    "#e11d48",  # rojo (sobre todo para tachado/subrayado)
}


def _normalizar_rects(valor):
    """Acepta [[x, y, ancho, alto], ...] con todo dentro de 0..1."""
    if not isinstance(valor, list) or not valor:
        raise ApiError("'rects' debe ser una lista no vacía de rectángulos")

    limpios = []
    for rect in valor:
        if not isinstance(rect, (list, tuple)) or len(rect) != 4:
            raise ApiError("cada rectángulo debe ser [x, y, ancho, alto]")
        try:
            x, y, ancho, alto = (float(v) for v in rect)
        except (TypeError, ValueError):
            raise ApiError("los rectángulos deben contener números")
        if ancho <= 0 or alto <= 0:
            continue  # rectángulo degenerado: no aporta nada, se descarta
        # Se recorta al área de la página en vez de rechazar: un redondeo del
        # navegador puede dejar un borde en 1.0000001 y no es motivo de error.
        x = min(max(x, 0.0), 1.0)
        y = min(max(y, 0.0), 1.0)
        ancho = min(ancho, 1.0 - x)
        alto = min(alto, 1.0 - y)
        if ancho <= 0 or alto <= 0:
            continue
        limpios.append([round(x, 6), round(y, 6), round(ancho, 6), round(alto, 6)])

    if not limpios:
        raise ApiError("'rects' no contiene ningún rectángulo válido")
    return limpios


def _validar_color(color):
    if color not in COLORES_ANOTACION:
        raise ApiError(f"color no permitido: {color}")
    return color


@anotaciones_bp.get("/documentos/<int:documento_id>/anotaciones")
def listar_anotaciones(documento_id):
    Documento.query.get_or_404(documento_id)
    anotaciones = (
        AnotacionPdf.query.filter_by(documento_id=documento_id)
        .order_by(AnotacionPdf.numero_pagina, AnotacionPdf.id)
        .all()
    )
    return jsonify([a.to_dict() for a in anotaciones])


@anotaciones_bp.post("/documentos/<int:documento_id>/anotaciones")
def crear_anotacion(documento_id):
    Documento.query.get_or_404(documento_id)
    data = request.get_json(silent=True) or {}

    if "numero_pagina" not in data:
        raise ApiError("'numero_pagina' es obligatorio")
    tipo = data.get("tipo", "resaltado")
    if tipo not in TIPOS_ANOTACION_PDF:
        raise ApiError(f"tipo debe ser uno de {TIPOS_ANOTACION_PDF}")

    anotacion = AnotacionPdf(
        documento_id=documento_id,
        numero_pagina=data["numero_pagina"],
        tipo=tipo,
        color=_validar_color(data.get("color", "#ffd400")),
        texto=(data.get("texto") or None),
        comentario=(data.get("comentario") or None),
        rects=json.dumps(_normalizar_rects(data.get("rects"))),
    )
    db.session.add(anotacion)
    db.session.commit()
    return jsonify(anotacion.to_dict()), 201


@anotaciones_bp.patch("/anotaciones/<int:anotacion_id>")
def actualizar_anotacion(anotacion_id):
    anotacion = AnotacionPdf.query.get_or_404(anotacion_id)
    data = request.get_json(silent=True) or {}

    if "color" in data:
        anotacion.color = _validar_color(data["color"])
    if "tipo" in data:
        if data["tipo"] not in TIPOS_ANOTACION_PDF:
            raise ApiError(f"tipo debe ser uno de {TIPOS_ANOTACION_PDF}")
        anotacion.tipo = data["tipo"]
    if "comentario" in data:
        anotacion.comentario = data["comentario"] or None

    db.session.commit()
    return jsonify(anotacion.to_dict())


@anotaciones_bp.delete("/anotaciones/<int:anotacion_id>")
def borrar_anotacion(anotacion_id):
    anotacion = AnotacionPdf.query.get_or_404(anotacion_id)
    db.session.delete(anotacion)
    db.session.commit()
    return "", 204
