"""
Test del buscador global (routes/busqueda.py) para Hitos y Conceptos: hasta ahora
/buscar no los incluía pese a tener su propia página/widget en la app. El resto de
/buscar (asignaturas, documentos, etc.) queda fuera de este archivo — no se ha
tocado en este cambio.
"""

import pytest


@pytest.fixture
def asignatura_id(client_abierto):
    return client_abierto.get("/asignaturas").get_json()[0]["id"]


def test_buscar_encuentra_hito_por_nombre(client_abierto):
    client_abierto.post("/hitos", json={"nombre": "Certificado AWS"})
    data = client_abierto.get("/buscar?q=aws").get_json()
    assert len(data["hitos"]) == 1
    assert data["hitos"][0]["nombre"] == "Certificado AWS"
    assert data["hitos"][0]["url"] == "/vista/dashboard"


def test_buscar_hito_no_coincide_no_aparece(client_abierto):
    client_abierto.post("/hitos", json={"nombre": "Certificado AWS"})
    data = client_abierto.get("/buscar?q=nada-que-coincida").get_json()
    assert data["hitos"] == []


def test_buscar_encuentra_concepto_con_asignatura(client_abierto, asignatura_id):
    client_abierto.post(f"/asignaturas/{asignatura_id}/conceptos", json={"nombre": "Transformada de Fourier"})
    data = client_abierto.get("/buscar?q=fourier").get_json()
    assert len(data["conceptos"]) == 1
    item = data["conceptos"][0]
    assert item["nombre"] == "Transformada de Fourier"
    assert item["asignatura_id"] == asignatura_id
    assert item["url"] == f"/vista/asignaturas/{asignatura_id}"


def test_hito_y_concepto_favoriteables(client_abierto):
    """TIPOS_ENTIDAD_BUSQUEDA (models.py) tiene que incluir 'hito' y 'concepto' o
    el endpoint de favoritos los rechaza con ValueError -> 400."""
    r1 = client_abierto.post("/busqueda/favoritos", json={"tipo_entidad": "hito", "entidad_id": 1})
    assert r1.status_code == 201
    r2 = client_abierto.post("/busqueda/favoritos", json={"tipo_entidad": "concepto", "entidad_id": 1})
    assert r2.status_code == 201
