import pytest
from datetime import date, timedelta


@pytest.fixture
def cuatri_id(client_abierto):
    anio = client_abierto.get("/anios").get_json()[0]
    return client_abierto.get(f"/anios/{anio['id']}").get_json()["cuatrimestres"][0]["id"]


def test_objetivo_media_calcula_la_nota_necesaria(client_abierto, cuatri_id):
    # El seed de tests no trae notas: todo son ECTS pendientes salvo lo que pongamos.
    base = client_abierto.get("/asignaturas/objetivo-media").get_json()
    a = client_abierto.post("/asignaturas", json={"cuatrimestre_id": cuatri_id, "nombre": "Hecha", "creditos_ects": 6}).get_json()["id"]
    client_abierto.put(f"/asignaturas/{a}", json={"nota_final": 9.0})

    assert client_abierto.put("/configuracion", json={"objetivo_media": 7}).status_code == 200
    r = client_abierto.get("/asignaturas/objetivo-media").get_json()
    pend = base["ects_pendientes"]
    assert r["objetivo"] == 7 and r["media_actual"] == 9.0 and r["ects_pendientes"] == pend
    assert r["nota_necesaria"] == pytest.approx((7 * (6 + pend) - 9 * 6) / pend, abs=0.01)
    assert r["alcanzable"] is True


def test_objetivo_ya_asegurado_e_inalcanzable(client_abierto, cuatri_id):
    a = client_abierto.post("/asignaturas", json={"cuatrimestre_id": cuatri_id, "nombre": "Hecha", "creditos_ects": 6}).get_json()["id"]
    client_abierto.put(f"/asignaturas/{a}", json={"nota_final": 10.0})
    client_abierto.put("/configuracion", json={"objetivo_media": 0})
    assert client_abierto.get("/asignaturas/objetivo-media").get_json()["nota_necesaria"] == 0
    client_abierto.put("/configuracion", json={"objetivo_media": 10})
    r = client_abierto.get("/asignaturas/objetivo-media").get_json()
    assert r["nota_necesaria"] == pytest.approx(10, abs=0.01)  # exactamente 10 en lo pendiente
    client_abierto.put(f"/asignaturas/{a}", json={"nota_final": 5.0})
    assert client_abierto.get("/asignaturas/objetivo-media").get_json()["alcanzable"] is False


def test_objetivo_valida_rango_y_admite_null(client_abierto):
    assert client_abierto.put("/configuracion", json={"objetivo_media": 11}).status_code == 400
    assert client_abierto.put("/configuracion", json={"objetivo_media": "alto"}).status_code == 400
    assert client_abierto.put("/configuracion", json={"objetivo_media": None}).status_code == 200
    assert client_abierto.get("/asignaturas/objetivo-media").get_json()["nota_necesaria"] is None


def test_media_por_cuatrimestre(client_abierto, cuatri_id):
    a = client_abierto.post("/asignaturas", json={"cuatrimestre_id": cuatri_id, "nombre": "Con nota", "creditos_ects": 6}).get_json()["id"]
    client_abierto.put(f"/asignaturas/{a}", json={"nota_final": 8.0})
    filas = client_abierto.get("/asignaturas/media-por-cuatrimestre").get_json()
    numero = client_abierto.get(f"/cuatrimestres/{cuatri_id}").get_json()["numero"]
    fila = next(f for f in filas if f["numero"] == numero)
    assert fila["media"] == 8.0 and fila["con_nota"] == 1 and fila["total"] >= 1
    assert all(f["media"] is None for f in filas if f["numero"] != numero)


def _tarea(client, dias, recordatorio=None):
    body = {"titulo": f"T{dias}-{recordatorio}", "fecha": (date.today() + timedelta(days=dias)).isoformat()}
    if recordatorio is not None:
        body["recordatorio"] = recordatorio
    return client.post("/tareas", json=body).get_json()["id"]


def test_recordatorio_de_la_tarea_manda_sobre_el_ajuste_general(client_abierto):
    en_5_con_2 = _tarea(client_abierto, 5, recordatorio=2)   # ajuste general 7 días, pero ella pide 2
    en_5_sin = _tarea(client_abierto, 5)                     # usa el general: avisa
    en_1_con_2 = _tarea(client_abierto, 1, recordatorio=2)   # dentro de su ventana: avisa
    ids = {n["entidad_id"] for n in client_abierto.get("/notificaciones").get_json() if n["tipo"] == "tarea"}
    assert en_5_con_2 not in ids
    assert en_5_sin in ids and en_1_con_2 in ids


def test_importar_ics_guarda_el_recordatorio(client_abierto):
    ev = {"titulo": "Con aviso", "fecha": "2026-10-09", "tipo": "entrega", "recordatorio": 3}
    assert client_abierto.post("/calendario/importar-ics", json={"eventos": [ev]}).status_code == 201
    tarea = next(t for t in client_abierto.get("/tareas").get_json() if t["titulo"] == "Con aviso")
    assert tarea["recordatorio"] == 3
    malo = dict(ev, titulo="Malo", recordatorio=-1)
    assert client_abierto.post("/calendario/importar-ics", json={"eventos": [malo]}).status_code == 400


def test_marcar_hecha_saca_la_tarea_de_las_notificaciones(client_abierto):
    tarea_id = _tarea(client_abierto, 1)
    assert tarea_id in {n["entidad_id"] for n in client_abierto.get("/notificaciones").get_json() if n["tipo"] == "tarea"}
    assert client_abierto.put(f"/tareas/{tarea_id}", json={"completada": True}).status_code == 200
    assert tarea_id not in {n["entidad_id"] for n in client_abierto.get("/notificaciones").get_json() if n["tipo"] == "tarea"}
    assert tarea_id not in {t["id"] for t in client_abierto.get("/tareas?completada=false").get_json()}


def test_horario_tiene_boton_de_imprimir(client_abierto):
    assert "btn-imprimir-horario" in client_abierto.get("/vista/horario").get_data(as_text=True)
