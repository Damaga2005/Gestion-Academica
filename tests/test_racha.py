"""
Racha de estudio: días consecutivos de actividad real (leer un documento,
completar una tarea, revisar un concepto), terminando hoy o ayer.
"""
from datetime import date, timedelta

import pytest


@pytest.fixture
def asignatura_id(client_abierto):
    return client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]


def test_sin_actividad_racha_es_cero(client_abierto):
    assert client_abierto.get("/racha").get_json()["dias"] == 0


def test_completar_tarea_cuenta_como_actividad_hoy(client_abierto):
    tarea = client_abierto.post("/tareas", json={
        "titulo": "Leer apuntes", "fecha": date.today().isoformat(), "tipo": "tarea_general",
    }).get_json()
    client_abierto.put(f"/tareas/{tarea['id']}", json={"completada": True})
    assert client_abierto.get("/racha").get_json()["dias"] == 1


def test_autocompletar_examen_pasado_no_cuenta_como_actividad(client_abierto, asignatura_id):
    """El autocompletado de exámenes pasados (routes/notificaciones.py) es una
    limpieza automática, no algo que el usuario haya hecho hoy: no debe inflar la
    racha con actividad falsa."""
    client_abierto.post("/tareas", json={
        "titulo": "Final", "fecha": (date.today() - timedelta(days=5)).isoformat(),
        "tipo": "examen_final", "asignatura_id": asignatura_id,
    })
    client_abierto.get("/notificaciones")  # dispara el autocompletado
    assert client_abierto.get("/racha").get_json()["dias"] == 0


def test_leer_documento_cuenta_como_actividad(client_abierto, asignatura_id):
    doc_id = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/teoria/documentos",
        data={"archivos": [(__import__("io").BytesIO(b"%PDF-1.4 x"), "t.pdf")]},
        content_type="multipart/form-data",
    ).get_json()[0]["id"]

    client_abierto.post(f"/documentos/{doc_id}/progreso", json={"pagina": 1})
    assert client_abierto.get("/racha").get_json()["dias"] == 1


def test_racha_no_se_rompe_si_ayer_hubo_actividad_pero_hoy_todavia_no(app_abierta, client_abierto):
    with app_abierta.app_context():
        from models import db, DiaActividad
        db.session.add(DiaActividad(fecha=date.today() - timedelta(days=1)))
        db.session.add(DiaActividad(fecha=date.today() - timedelta(days=2)))
        db.session.commit()
    assert client_abierto.get("/racha").get_json()["dias"] == 2


def test_racha_se_rompe_si_falta_un_dia(app_abierta, client_abierto):
    with app_abierta.app_context():
        from models import db, DiaActividad
        db.session.add(DiaActividad(fecha=date.today() - timedelta(days=2)))
        db.session.add(DiaActividad(fecha=date.today() - timedelta(days=3)))
        db.session.commit()
    assert client_abierto.get("/racha").get_json()["dias"] == 0


def test_racha_record_es_la_mas_larga_de_la_historia_no_la_actual(app_abierta, client_abierto):
    with app_abierta.app_context():
        from models import db, DiaActividad
        # racha vieja de 3 días, rota, y la actual de 1 día (hoy)
        for hace_dias in (10, 11, 12):
            db.session.add(DiaActividad(fecha=date.today() - timedelta(days=hace_dias)))
        db.session.commit()
    r = client_abierto.post("/tareas", json={
        "titulo": "Hoy", "fecha": date.today().isoformat(), "tipo": "tarea_general",
    }).get_json()
    client_abierto.put(f"/tareas/{r['id']}", json={"completada": True})

    respuesta = client_abierto.get("/racha").get_json()
    assert respuesta["dias"] == 1
    assert respuesta["record"] == 3
