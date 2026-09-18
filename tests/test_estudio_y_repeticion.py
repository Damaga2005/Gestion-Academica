import pytest
from datetime import date, timedelta


@pytest.fixture
def asignatura_id(client_abierto):
    anio = client_abierto.get("/anios").get_json()[0]
    cuatri = client_abierto.get(f"/anios/{anio['id']}").get_json()["cuatrimestres"][0]["id"]
    return client_abierto.post("/asignaturas", json={"cuatrimestre_id": cuatri, "nombre": "Estudio", "creditos_ects": 6, "siglas": "ZZE"}).get_json()["id"]


def test_sesion_suma_minutos_y_cuenta_para_la_racha(client_abierto, asignatura_id):
    racha_antes = client_abierto.get("/racha").get_json()["dias"]
    r = client_abierto.post("/estudio/sesiones", json={"minutos": 25, "asignatura_id": asignatura_id})
    assert r.status_code == 201
    client_abierto.post("/estudio/sesiones", json={"minutos": 30})  # sin asignatura
    res = client_abierto.get("/estudio/resumen").get_json()
    assert res["hoy_min"] == 55 and res["semana_min"] == 55
    assert res["por_asignatura"] == [{"asignatura": "ZZE", "minutos": 25}]
    assert client_abierto.get("/racha").get_json()["dias"] >= max(racha_antes, 1)


@pytest.mark.parametrize("cuerpo", [{"minutos": 0}, {"minutos": 601}, {"minutos": "25"}, {}, {"minutos": 25, "asignatura_id": 99999}])
def test_sesion_valida_entrada(client_abierto, cuerpo):
    assert client_abierto.post("/estudio/sesiones", json=cuerpo).status_code == 400


def _crear(client, **extra):
    body = {"titulo": "Seminario", "fecha": "2026-10-05", "tipo": "evento", **extra}
    return client.post("/tareas", json=body)


def test_repetir_semanalmente_crea_copias(client_abierto):
    r = _crear(client_abierto, repetir_semanas=3, hora_inicio="10:00", hora_fin="11:00")
    assert r.status_code == 201 and r.get_json()["copias_creadas"] == 3
    fechas = sorted(t["fecha"] for t in client_abierto.get("/tareas").get_json() if t["titulo"] == "Seminario")
    assert fechas == ["2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"]
    assert all(t["hora_inicio"].startswith("10:00") for t in client_abierto.get("/tareas").get_json() if t["titulo"] == "Seminario")


def test_repetir_valida_y_no_permite_examenes(client_abierto):
    assert _crear(client_abierto, repetir_semanas=53).status_code == 400
    assert _crear(client_abierto, repetir_semanas="x").status_code == 400
    assert _crear(client_abierto, tipo="examen_parcial", repetir_semanas=2).status_code == 400
    assert _crear(client_abierto).get_json()["copias_creadas"] == 0


def test_paginas_cargan_temporizador_y_repeticion(client_abierto):
    dash = client_abierto.get("/vista/dashboard").get_data(as_text=True) if client_abierto.get("/vista/dashboard").status_code == 200 else client_abierto.get("/").get_data(as_text=True)
    assert "temp-iniciar" in dash and "temporizador.js" in dash and "seccion-semana" in dash
    assert "tarea-repetir" in client_abierto.get("/vista/calendario").get_data(as_text=True)
