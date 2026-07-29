"""
Tests del indicador "Estado de las Asignaturas" (🟢/🟡/🔴/⚪, calcular_estado_notas
en models.py) y de "Media del Curso" (GET /asignaturas/media-curso). Ninguno de
los dos toca el campo `estado` manual existente.
"""

import pytest


@pytest.fixture
def cuatrimestre_id(client_abierto):
    anio = client_abierto.get("/anios").get_json()[0]
    detalle = client_abierto.get(f"/anios/{anio['id']}").get_json()
    return detalle["cuatrimestres"][0]["id"]


def _crear_asignatura(client, cuatrimestre_id, nombre):
    r = client.post("/asignaturas", json={
        "cuatrimestre_id": cuatrimestre_id, "nombre": nombre, "creditos_ects": 6,
    })
    assert r.status_code == 201
    return r.get_json()["id"]


def _crear_componente(client, asignatura_id, esquema_id, porcentaje, nota=None):
    r = client.post(f"/esquemas/{esquema_id}/componentes", json={
        "nombre": "Componente", "tipo": "otro", "porcentaje": porcentaje, "nota": nota,
    })
    assert r.status_code == 201
    return r.get_json()["id"]


def _primer_esquema_id(client, asignatura_id):
    r = client.post(f"/asignaturas/{asignatura_id}/esquemas", json={"nombre": "Evaluación continua"})
    assert r.status_code == 201
    return r.get_json()["id"]


# --- calcular_estado_notas vía GET /asignaturas/<id> ---

def test_sin_componentes_ni_nota_es_sin_evaluar(client_abierto, cuatrimestre_id):
    aid = _crear_asignatura(client_abierto, cuatrimestre_id, "Sin evaluar")
    data = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert data["estado_notas"] == "sin_evaluar"
    assert data["nota_actual"] is None
    assert data["evaluaciones_realizadas"] == 0


def test_nota_final_directa_manda_sobre_componentes(client_abierto, cuatrimestre_id):
    aid = _crear_asignatura(client_abierto, cuatrimestre_id, "Nota directa")
    client_abierto.put(f"/asignaturas/{aid}", json={"nota_final": 7.5})
    data = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert data["estado_notas"] == "aprobada"
    assert data["nota_actual"] == 7.5


def test_umbral_exacto_5_es_aprobada(client_abierto, cuatrimestre_id):
    aid = _crear_asignatura(client_abierto, cuatrimestre_id, "Umbral 5")
    client_abierto.put(f"/asignaturas/{aid}", json={"nota_final": 5.0})
    assert client_abierto.get(f"/asignaturas/{aid}").get_json()["estado_notas"] == "aprobada"


def test_justo_debajo_del_umbral_es_suspendida(client_abierto, cuatrimestre_id):
    aid = _crear_asignatura(client_abierto, cuatrimestre_id, "Umbral 4.99")
    client_abierto.put(f"/asignaturas/{aid}", json={"nota_final": 4.99})
    assert client_abierto.get(f"/asignaturas/{aid}").get_json()["estado_notas"] == "suspendida"


def test_parcialmente_evaluada_es_en_progreso(client_abierto, cuatrimestre_id):
    aid = _crear_asignatura(client_abierto, cuatrimestre_id, "Parcial")
    esquema_id = _primer_esquema_id(client_abierto, aid)
    _crear_componente(client_abierto, aid, esquema_id, porcentaje=50, nota=8.0)
    _crear_componente(client_abierto, aid, esquema_id, porcentaje=50, nota=None)

    data = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert data["estado_notas"] == "en_progreso"
    assert data["nota_actual"] is None
    assert data["evaluaciones_realizadas"] == 1
    assert data["evaluaciones_pendientes"] == 1


def test_totalmente_evaluada_por_componentes_aprobada(client_abierto, cuatrimestre_id):
    aid = _crear_asignatura(client_abierto, cuatrimestre_id, "Completa aprobada")
    esquema_id = _primer_esquema_id(client_abierto, aid)
    _crear_componente(client_abierto, aid, esquema_id, porcentaje=60, nota=8.0)
    _crear_componente(client_abierto, aid, esquema_id, porcentaje=40, nota=6.0)

    data = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert data["estado_notas"] == "aprobada"
    assert data["nota_actual"] == pytest.approx(0.6 * 8.0 + 0.4 * 6.0)
    assert data["evaluaciones_pendientes"] == 0


def test_totalmente_evaluada_por_componentes_suspendida(client_abierto, cuatrimestre_id):
    aid = _crear_asignatura(client_abierto, cuatrimestre_id, "Completa suspendida")
    esquema_id = _primer_esquema_id(client_abierto, aid)
    _crear_componente(client_abierto, aid, esquema_id, porcentaje=100, nota=3.0)

    data = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert data["estado_notas"] == "suspendida"
    assert data["nota_actual"] == 3.0


def test_varios_esquemas_regla_maximo(client_abierto, cuatrimestre_id):
    """Con dos esquemas alternativos, cuenta el de mejor media_ponderada (regla
    'maximo', igual que esquemas_con_ganador) siempre que esté al 100% evaluado."""
    aid = _crear_asignatura(client_abierto, cuatrimestre_id, "Dos esquemas")
    esquema_1 = _primer_esquema_id(client_abierto, aid)
    _crear_componente(client_abierto, aid, esquema_1, porcentaje=100, nota=4.0)

    esquema_2 = client_abierto.post(f"/asignaturas/{aid}/esquemas", json={"nombre": "Alternativa"}).get_json()["id"]
    _crear_componente(client_abierto, aid, esquema_2, porcentaje=100, nota=9.0)

    data = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert data["estado_notas"] == "aprobada"
    assert data["nota_actual"] == 9.0


def test_estado_notas_no_toca_estado_manual(client_abierto, cuatrimestre_id):
    aid = _crear_asignatura(client_abierto, cuatrimestre_id, "Estado intacto")
    client_abierto.put(f"/asignaturas/{aid}", json={"nota_final": 9.0})
    data = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert data["estado"] == "pendiente"  # valor por defecto, sin tocar
    assert data["estado_notas"] == "aprobada"


# --- GET /asignaturas/media-curso ---

def test_media_curso_sin_notas(client_abierto):
    r = client_abierto.get("/asignaturas/media-curso")
    assert r.status_code == 200
    data = r.get_json()
    assert data["media_general"] is None
    assert data["nota_mas_alta"] is None
    assert data["nota_mas_baja"] is None
    assert data["aprobadas"] == 0


def test_media_curso_agrega_correctamente(client_abierto, cuatrimestre_id):
    antes = client_abierto.get("/asignaturas/media-curso").get_json()

    aid_alta = _crear_asignatura(client_abierto, cuatrimestre_id, "Media alta")
    client_abierto.put(f"/asignaturas/{aid_alta}", json={"nota_final": 9.0})
    aid_baja = _crear_asignatura(client_abierto, cuatrimestre_id, "Media baja")
    client_abierto.put(f"/asignaturas/{aid_baja}", json={"nota_final": 3.0})

    despues = client_abierto.get("/asignaturas/media-curso").get_json()
    assert despues["total"] == antes["total"] + 2
    assert despues["aprobadas"] == antes["aprobadas"] + 1
    assert despues["suspendidas"] == antes["suspendidas"] + 1
    assert despues["nota_mas_alta"] == 9.0
    assert despues["nota_mas_baja"] == 3.0
    assert despues["media_general"] == pytest.approx((9.0 + 3.0) / 2)
