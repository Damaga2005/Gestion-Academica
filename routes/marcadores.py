from flask import Blueprint, request, jsonify

from models import db, Marcador, Documento
from routes.errors import ApiError

marcadores_bp = Blueprint("marcadores", __name__)


@marcadores_bp.get("/documentos/<int:documento_id>/marcadores")
def listar_marcadores(documento_id):
    Documento.query.get_or_404(documento_id)
    marcadores = Marcador.query.filter_by(documento_id=documento_id).order_by(Marcador.numero_pagina).all()
    return jsonify([m.to_dict() for m in marcadores])


@marcadores_bp.post("/documentos/<int:documento_id>/marcadores")
def crear_marcador(documento_id):
    Documento.query.get_or_404(documento_id)
    data = request.get_json(silent=True) or {}
    if "numero_pagina" not in data:
        raise ApiError("'numero_pagina' es obligatorio")

    marcador = Marcador(
        documento_id=documento_id,
        numero_pagina=data["numero_pagina"],
        titulo=data.get("titulo"),
    )
    db.session.add(marcador)
    db.session.commit()
    return jsonify(marcador.to_dict()), 201


@marcadores_bp.put("/marcadores/<int:marcador_id>")
def actualizar_marcador(marcador_id):
    marcador = Marcador.query.get_or_404(marcador_id)
    data = request.get_json(silent=True) or {}
    if "numero_pagina" in data:
        marcador.numero_pagina = data["numero_pagina"]
    if "titulo" in data:
        marcador.titulo = data["titulo"]
    db.session.commit()
    return jsonify(marcador.to_dict())


@marcadores_bp.delete("/marcadores/<int:marcador_id>")
def borrar_marcador(marcador_id):
    marcador = Marcador.query.get_or_404(marcador_id)
    db.session.delete(marcador)
    db.session.commit()
    return "", 204
