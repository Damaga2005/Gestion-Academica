"""Línea de tiempo del cuatrimestre: horario (barra) + exámenes/entregas (marcadores)
por asignatura del cuatrimestre marcado como "actual"."""
from datetime import date, timedelta

import pytest


@pytest.fixture
def asignatura_id(client_abierto, app_abierta):
    """Una asignatura del cuatrimestre marcado como "actual" — /linea-tiempo solo
    incluye ese cuatrimestre, así que cualquier otra quedaría fuera sin más."""
    with app_abierta.app_context():
        from models import Asignatura, Cuatrimestre
        cuatrimestre = Cuatrimestre.query.filter_by(estado="actual").first()
        return Asignatura.query.filter_by(cuatrimestre_id=cuatrimestre.id).first().id


def test_sin_cuatrimestre_actual_devuelve_vacio(client_abierto, app_abierta):
    with app_abierta.app_context():
        from models import db, Cuatrimestre
        for c in Cuatrimestre.query.filter_by(estado="actual").all():
            c.estado = "superado"
        db.session.commit()

    data = client_abierto.get("/linea-tiempo").get_json()
    assert data["filas"] == []


def test_incluye_horario_y_eventos_de_la_asignatura(client_abierto, asignatura_id):
    client_abierto.post("/horarios", json={
        "asignatura_id": asignatura_id, "tipo": "teoria", "dia_semana": 1,
        "hora_inicio": "09:00", "hora_fin": "11:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18", "intervalo_semanas": 1,
    })
    client_abierto.post("/tareas", json={
        "titulo": "Parcial", "fecha": "2026-11-10",
        "tipo": "examen_parcial", "asignatura_id": asignatura_id,
    })

    data = client_abierto.get("/linea-tiempo").get_json()
    fila = next(f for f in data["filas"] if f["asignatura_id"] == asignatura_id)
    assert fila["barra"] == {"inicio": "2026-09-07", "fin": "2026-12-18"}
    assert len(fila["marcadores"]) == 1
    assert fila["marcadores"][0]["titulo"] == "Parcial"
    # el rango cubre tanto el horario como el examen, con margen
    assert data["rango"]["inicio"] <= "2026-09-07"
    assert data["rango"]["fin"] >= "2026-12-18"


def test_asignatura_sin_nada_temporal_no_aparece(client_abierto, asignatura_id):
    data = client_abierto.get("/linea-tiempo").get_json()
    assert not any(f["asignatura_id"] == asignatura_id for f in data["filas"])


def test_asignatura_de_otro_cuatrimestre_no_aparece(client_abierto, app_abierta, asignatura_id):
    with app_abierta.app_context():
        from models import db, Asignatura, Cuatrimestre
        otro = Cuatrimestre.query.filter(Cuatrimestre.estado != "actual").first()
        Asignatura.query.get(asignatura_id).cuatrimestre_id = otro.id
        db.session.commit()

    client_abierto.post("/tareas", json={
        "titulo": "Examen futuro", "fecha": (date.today() + timedelta(days=200)).isoformat(),
        "tipo": "examen_final", "asignatura_id": asignatura_id,
    })
    data = client_abierto.get("/linea-tiempo").get_json()
    assert not any(f["asignatura_id"] == asignatura_id for f in data["filas"])
