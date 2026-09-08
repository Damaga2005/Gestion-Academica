from flask import Blueprint, jsonify

from models import calcular_racha_actual, calcular_racha_maxima

racha_bp = Blueprint("racha", __name__)


@racha_bp.get("/racha")
def obtener_racha():
    return jsonify({"dias": calcular_racha_actual(), "record": calcular_racha_maxima()})
