from flask import Blueprint, request, jsonify

from models import db, NotaRapida
from routes.errors import ApiError

notas_rapidas_bp = Blueprint("notas_rapidas", __name__)


@notas_rapidas_bp.get("/notas-rapidas")
def listar_notas_rapidas():
    notas = NotaRapida.query.order_by(NotaRapida.fecha_creacion.desc()).all()
    return jsonify([n.to_dict() for n in notas])


@notas_rapidas_bp.post("/notas-rapidas")
def crear_nota_rapida():
    data = request.get_json(silent=True) or {}
    if not (data.get("texto") or "").strip():
        raise ApiError("'texto' es obligatorio")

    nota = NotaRapida(texto=data["texto"])
    db.session.add(nota)
    db.session.commit()
    return jsonify(nota.to_dict()), 201


@notas_rapidas_bp.delete("/notas-rapidas/<int:nota_id>")
def borrar_nota_rapida(nota_id):
    nota = NotaRapida.query.get_or_404(nota_id)
    db.session.delete(nota)
    db.session.commit()
    return "", 204
