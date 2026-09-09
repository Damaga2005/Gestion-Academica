"""
Tests de Notificaciones (calcular_notificaciones en routes/notificaciones.py):
tareas atrasadas/próximas + asignaturas "cursando" sin actividad reciente. Sin
test previo pese a construirse enteramente sobre configuración (dias_aviso_examen,
dias_asignatura_abandonada) y aritmética de fechas.
"""

import io
from datetime import date, datetime, timedelta

import pytest


@pytest.fixture
def asignatura_id(client_abierto):
    return client_abierto.get("/asignaturas").get_json()[0]["id"]


@pytest.fixture
def documento_id(client_abierto, asignatura_id):
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/teoria/documentos",
        data={"archivos": [(io.BytesIO(b"%PDF-1.4 x"), "t.pdf")]},
        content_type="multipart/form-data",
    )
    return r.get_json()[0]["id"]


def _crear_tarea(client, fecha, **extra):
    r = client.post("/tareas", json={"titulo": "Tarea de prueba", "fecha": fecha.isoformat(), **extra})
    assert r.status_code == 201
    return r.get_json()


# --- Tareas atrasadas / próximas ---

def test_tarea_atrasada_es_nivel_rojo(client_abierto):
    _crear_tarea(client_abierto, date.today() - timedelta(days=2))
    notif = client_abierto.get("/notificaciones").get_json()
    assert any(n["nivel"] == "rojo" and "atrasada" in n["mensaje"] for n in notif)


def test_examen_pasado_se_autocompleta_en_vez_de_salir_atrasado(client_abierto):
    tarea = _crear_tarea(client_abierto, date.today() - timedelta(days=2), tipo="examen_parcial")
    notif = client_abierto.get("/notificaciones").get_json()
    assert not any(n["titulo"] == "Tarea de prueba" for n in notif)

    r = client_abierto.get(f"/tareas/{tarea['id']}")
    assert r.get_json()["completada"] is True


def test_tarea_general_pasada_sigue_atrasada_no_se_autocompleta(client_abierto):
    tarea = _crear_tarea(client_abierto, date.today() - timedelta(days=2), tipo="entrega")
    client_abierto.get("/notificaciones")
    r = client_abierto.get(f"/tareas/{tarea['id']}")
    assert r.get_json()["completada"] is False


# --- Descartar un aviso por hoy ---

def test_descartar_quita_el_aviso_de_la_lista(client_abierto):
    tarea = _crear_tarea(client_abierto, date.today() - timedelta(days=1))
    notif = client_abierto.get("/notificaciones").get_json()
    aviso = next(n for n in notif if n["titulo"] == "Tarea de prueba")

    r = client_abierto.post("/notificaciones/descartar", json={
        "tipo": aviso["tipo"], "entidad_id": aviso["entidad_id"],
    })
    assert r.status_code == 204

    notif2 = client_abierto.get("/notificaciones").get_json()
    assert not any(n["titulo"] == "Tarea de prueba" for n in notif2)


def test_descartar_no_completa_la_tarea(client_abierto):
    tarea = _crear_tarea(client_abierto, date.today() - timedelta(days=1))
    client_abierto.post("/notificaciones/descartar", json={"tipo": "tarea", "entidad_id": tarea["id"]})
    r = client_abierto.get(f"/tareas/{tarea['id']}")
    assert r.get_json()["completada"] is False


def test_descartar_es_idempotente(client_abierto):
    tarea = _crear_tarea(client_abierto, date.today() - timedelta(days=1))
    body = {"tipo": "tarea", "entidad_id": tarea["id"]}
    assert client_abierto.post("/notificaciones/descartar", json=body).status_code == 204
    assert client_abierto.post("/notificaciones/descartar", json=body).status_code == 204


def test_descartar_sin_campos_da_error(client_abierto):
    r = client_abierto.post("/notificaciones/descartar", json={})
    assert r.status_code == 400


def test_descartar_limpia_filas_de_dias_anteriores(app_abierta, client_abierto):
    with app_abierta.app_context():
        from models import db, AvisoDescartado
        db.session.add(AvisoDescartado(tipo="tarea", entidad_id=999, fecha=date.today() - timedelta(days=5)))
        db.session.commit()

    tarea = _crear_tarea(client_abierto, date.today() - timedelta(days=1))
    client_abierto.post("/notificaciones/descartar", json={"tipo": "tarea", "entidad_id": tarea["id"]})

    with app_abierta.app_context():
        from models import AvisoDescartado
        restantes = AvisoDescartado.query.all()
        assert len(restantes) == 1
        assert restantes[0].fecha == date.today()


# --- Examen próximo sin empezar a repasar (Espacio de Estudio en 0%) ---

def test_examen_proximo_sin_leer_nada_avisa(client_abierto, asignatura_id, documento_id):
    tarea = client_abierto.post("/tareas", json={
        "titulo": "Final", "fecha": (date.today() + timedelta(days=2)).isoformat(),
        "tipo": "examen_final", "asignatura_id": asignatura_id,
    }).get_json()
    espacio_id = client_abierto.get(f"/tareas/{tarea['id']}/espacio-estudio").get_json()["id"]
    client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "teoria",
    })

    notif = client_abierto.get("/notificaciones").get_json()
    assert any(n["tipo"] == "espacio_sin_empezar" and n["titulo"] == "Final" for n in notif)


def test_examen_proximo_con_algo_leido_no_avisa(client_abierto, asignatura_id, documento_id):
    tarea = client_abierto.post("/tareas", json={
        "titulo": "Final", "fecha": (date.today() + timedelta(days=2)).isoformat(),
        "tipo": "examen_final", "asignatura_id": asignatura_id,
    }).get_json()
    espacio_id = client_abierto.get(f"/tareas/{tarea['id']}/espacio-estudio").get_json()["id"]
    ref = client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "teoria",
    }).get_json()
    client_abierto.put(f"/espacios-estudio/documentos/{ref['id']}", json={"leido": True})

    notif = client_abierto.get("/notificaciones").get_json()
    assert not any(n["tipo"] == "espacio_sin_empezar" for n in notif)


def test_examen_lejano_sin_leer_no_avisa_todavia(client_abierto, asignatura_id, documento_id):
    tarea = client_abierto.post("/tareas", json={
        "titulo": "Final", "fecha": (date.today() + timedelta(days=10)).isoformat(),
        "tipo": "examen_final", "asignatura_id": asignatura_id,
    }).get_json()
    espacio_id = client_abierto.get(f"/tareas/{tarea['id']}/espacio-estudio").get_json()["id"]
    client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "teoria",
    })

    notif = client_abierto.get("/notificaciones").get_json()
    assert not any(n["tipo"] == "espacio_sin_empezar" for n in notif)


def test_espacio_sin_documentos_no_avisa(client_abierto, asignatura_id):
    client_abierto.post("/tareas", json={
        "titulo": "Final", "fecha": (date.today() + timedelta(days=1)).isoformat(),
        "tipo": "examen_final", "asignatura_id": asignatura_id,
    })
    notif = client_abierto.get("/notificaciones").get_json()
    assert not any(n["tipo"] == "espacio_sin_empezar" for n in notif)


def test_tarea_a_menos_de_3_dias_es_rojo(client_abierto):
    _crear_tarea(client_abierto, date.today() + timedelta(days=2))
    notif = client_abierto.get("/notificaciones").get_json()
    assert any(n["nivel"] == "rojo" and "atrasada" not in n["mensaje"] for n in notif)


def test_tarea_dentro_del_aviso_pero_no_inminente_es_naranja(client_abierto):
    # default dias_aviso_examen=7: 5 días cae dentro del aviso pero no en la zona roja (<3)
    _crear_tarea(client_abierto, date.today() + timedelta(days=5))
    notif = client_abierto.get("/notificaciones").get_json()
    assert any(n["nivel"] == "naranja" for n in notif)


def test_tarea_fuera_del_plazo_de_aviso_no_aparece(client_abierto):
    _crear_tarea(client_abierto, date.today() + timedelta(days=30))
    notif = client_abierto.get("/notificaciones").get_json()
    assert notif == []


def test_tarea_completada_no_genera_aviso(client_abierto):
    _crear_tarea(client_abierto, date.today() - timedelta(days=1), completada=True)
    notif = client_abierto.get("/notificaciones").get_json()
    assert notif == []


def test_aviso_respeta_config_dias_aviso_examen(client_abierto):
    client_abierto.put("/configuracion", json={"dias_aviso_examen": 20})
    _crear_tarea(client_abierto, date.today() + timedelta(days=15))
    notif = client_abierto.get("/notificaciones").get_json()
    assert len(notif) == 1


def test_orden_rojo_antes_que_naranja(client_abierto):
    _crear_tarea(client_abierto, date.today() + timedelta(days=5), titulo="Naranja")
    _crear_tarea(client_abierto, date.today() + timedelta(days=1), titulo="Roja")
    niveles = [n["nivel"] for n in client_abierto.get("/notificaciones").get_json()]
    assert niveles.index("rojo") < niveles.index("naranja")


# --- Asignatura "cursando" sin actividad reciente ---

def _marcar_cursando_con_actividad(app, asignatura_id, hace_dias):
    """Simula una asignatura cursando con notas editadas hace X días: la API siempre
    pone notas_actualizado_en=ahora, así que la fecha pasada se fuerza directo en BD."""
    with app.app_context():
        from models import db, Asignatura
        a = db.session.get(Asignatura, asignatura_id)
        a.estado = "cursando"
        a.notas = "algo"
        a.notas_actualizado_en = datetime.utcnow() - timedelta(days=hace_dias)
        db.session.commit()


def test_asignatura_cursando_inactiva_genera_aviso_gris(app_abierta, client_abierto, asignatura_id):
    _marcar_cursando_con_actividad(app_abierta, asignatura_id, hace_dias=20)  # > default 14
    notif = client_abierto.get("/notificaciones").get_json()
    assert any(n["tipo"] == "asignatura_inactiva" and n["nivel"] == "gris" for n in notif)


def test_asignatura_cursando_con_actividad_reciente_no_avisa(app_abierta, client_abierto, asignatura_id):
    _marcar_cursando_con_actividad(app_abierta, asignatura_id, hace_dias=1)
    notif = client_abierto.get("/notificaciones").get_json()
    assert not any(n["tipo"] == "asignatura_inactiva" for n in notif)


def test_asignatura_cursando_sin_actividad_previa_no_avisa(client_abierto, asignatura_id):
    # cursando pero sin notas ni documentos nunca registrados: no hay fecha base para
    # medir "inactivo desde cuándo", así que calcular_notificaciones la deja fuera.
    client_abierto.put(f"/asignaturas/{asignatura_id}", json={"estado": "cursando"})
    notif = client_abierto.get("/notificaciones").get_json()
    assert not any(n["tipo"] == "asignatura_inactiva" for n in notif)


def test_asignatura_no_cursando_nunca_avisa_por_inactividad(app_abierta, client_abierto, asignatura_id):
    with app_abierta.app_context():
        from models import db, Asignatura
        a = db.session.get(Asignatura, asignatura_id)
        a.estado = "pendiente"
        db.session.commit()
    notif = client_abierto.get("/notificaciones").get_json()
    assert not any(n["tipo"] == "asignatura_inactiva" for n in notif)
