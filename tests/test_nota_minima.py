import pytest


@pytest.fixture
def cuatri_id(client_abierto):
    anio = client_abierto.get("/anios").get_json()[0]
    return client_abierto.get(f"/anios/{anio['id']}").get_json()["cuatrimestres"][0]["id"]


@pytest.fixture
def asig(client_abierto, cuatri_id):
    aid = client_abierto.post("/asignaturas", json={"cuatrimestre_id": cuatri_id, "nombre": "Con mínimo", "creditos_ects": 6}).get_json()["id"]
    eid = client_abierto.post(f"/asignaturas/{aid}/esquemas", json={"nombre": "Evaluación"}).get_json()["id"]
    return aid, eid


def _comp(client, eid, porcentaje, nota, minimo=None):
    cid = client.post(f"/esquemas/{eid}/componentes", json={"nombre": "C", "porcentaje": porcentaje, "nota": nota}).get_json()["id"]
    if minimo is not None:
        assert client.put(f"/componentes/{cid}", json={"nota_minima": minimo}).status_code == 200
    return cid


def test_media_aprobada_pero_minimo_incumplido_suspende(client_abierto, asig):
    aid, eid = asig
    _comp(client_abierto, eid, 30, 10)                 # media total = 10*.3 + 3*.7 = 5.1 → aprobaría
    _comp(client_abierto, eid, 70, 3, minimo=4)        # pero el examen exige mínimo 4
    a = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert a["nota_actual"] == pytest.approx(5.1)
    assert a["minimo_incumplido"] is True
    assert a["estado_notas"] == "suspendida"


def test_minimo_cumplido_aprueba_y_sin_minimo_no_cambia_nada(client_abierto, asig):
    aid, eid = asig
    _comp(client_abierto, eid, 30, 10)
    _comp(client_abierto, eid, 70, 4, minimo=4)        # justo en el mínimo: cumple
    a = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert a["minimo_incumplido"] is False and a["estado_notas"] == "aprobada"


def test_nota_final_manual_ignora_los_minimos(client_abierto, asig):
    aid, eid = asig
    _comp(client_abierto, eid, 100, 2, minimo=4)
    client_abierto.put(f"/asignaturas/{aid}", json={"nota_final": 6})
    a = client_abierto.get(f"/asignaturas/{aid}").get_json()
    assert a["minimo_incumplido"] is False and a["estado_notas"] == "aprobada"


def test_nota_minima_validacion_y_duplicar(client_abierto, asig):
    aid, eid = asig
    cid = _comp(client_abierto, eid, 100, None, minimo=4)
    assert client_abierto.put(f"/componentes/{cid}", json={"nota_minima": 11}).status_code == 400
    assert client_abierto.put(f"/componentes/{cid}", json={"nota_minima": "x"}).status_code == 400
    copia = client_abierto.post(f"/esquemas/{eid}/duplicar").get_json()
    assert copia["componentes"][0]["nota_minima"] == 4
    assert client_abierto.put(f"/componentes/{cid}", json={"nota_minima": None}).get_json()["nota_minima"] is None
