"""
Tests de Conceptos/Repaso (repetición espaciada simplificada, spec punto 7):
routes/conceptos.py + Concepto.reclasificar() en models.py. Sin test previo pese
a llevar lógica real (niveles, intervalos, fecha de próxima revisión).
"""

from datetime import date, timedelta

import pytest


@pytest.fixture
def asignatura_id(client_abierto):
    return client_abierto.get("/asignaturas").get_json()[0]["id"]


def _crear_concepto(client, asignatura_id, nombre="Concepto de prueba"):
    r = client.post(f"/asignaturas/{asignatura_id}/conceptos", json={"nombre": nombre})
    assert r.status_code == 201
    return r.get_json()


# --- CRUD básico ---

def test_crear_concepto_nace_no_visto_y_revisable_hoy(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id)
    assert data["estado"] == "no_visto"
    assert data["proxima_revision"] == date.today().isoformat()
    assert data["ultima_revision"] is None
    assert data["asignatura_id"] == asignatura_id


def test_crear_concepto_sin_nombre_falla(client_abierto, asignatura_id):
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/conceptos", json={})
    assert r.status_code == 400


def test_crear_concepto_en_asignatura_inexistente_404(client_abierto):
    r = client_abierto.post("/asignaturas/999999/conceptos", json={"nombre": "X"})
    assert r.status_code == 404


def test_listar_conceptos_de_una_asignatura(client_abierto, asignatura_id):
    _crear_concepto(client_abierto, asignatura_id, "A")
    _crear_concepto(client_abierto, asignatura_id, "B")
    r = client_abierto.get(f"/asignaturas/{asignatura_id}/conceptos")
    nombres = {c["nombre"] for c in r.get_json()}
    assert nombres == {"A", "B"}


def test_actualizar_concepto_renombra(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id, "Antes")
    r = client_abierto.put(f"/conceptos/{data['id']}", json={"nombre": "Después"})
    assert r.get_json()["nombre"] == "Después"


def test_borrar_concepto(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id)
    assert client_abierto.delete(f"/conceptos/{data['id']}").status_code == 204
    assert client_abierto.put(f"/conceptos/{data['id']}", json={"nombre": "x"}).status_code == 404


# --- Reclasificar (repetición espaciada) ---

def test_subir_de_no_visto_a_flojo_fija_proxima_revision_en_3_dias(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id)
    r = client_abierto.post(f"/conceptos/{data['id']}/subir")
    actualizado = r.get_json()
    assert actualizado["estado"] == "flojo"
    assert actualizado["ultima_revision"] == date.today().isoformat()
    assert actualizado["proxima_revision"] == (date.today() + timedelta(days=3)).isoformat()


def test_subir_dos_veces_llega_a_dominado_18_dias(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id)
    client_abierto.post(f"/conceptos/{data['id']}/subir")
    r = client_abierto.post(f"/conceptos/{data['id']}/subir")
    actualizado = r.get_json()
    assert actualizado["estado"] == "dominado"
    assert actualizado["proxima_revision"] == (date.today() + timedelta(days=18)).isoformat()


def test_subir_en_dominado_se_queda_en_dominado(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id)
    client_abierto.post(f"/conceptos/{data['id']}/subir")
    client_abierto.post(f"/conceptos/{data['id']}/subir")
    r = client_abierto.post(f"/conceptos/{data['id']}/subir")  # ya estaba en dominado
    assert r.get_json()["estado"] == "dominado"


def test_bajar_en_no_visto_se_queda_en_no_visto(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id)
    r = client_abierto.post(f"/conceptos/{data['id']}/bajar")
    assert r.get_json()["estado"] == "no_visto"


def test_subir_y_bajar_vuelve_al_nivel_anterior(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id)
    client_abierto.post(f"/conceptos/{data['id']}/subir")  # no_visto -> flojo
    r = client_abierto.post(f"/conceptos/{data['id']}/bajar")  # flojo -> no_visto
    assert r.get_json()["estado"] == "no_visto"


# --- /repaso-hoy ---

def test_repaso_hoy_incluye_conceptos_con_revision_vencida(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id, "Pendiente hoy")
    r = client_abierto.get("/repaso-hoy")
    ids = [c["id"] for c in r.get_json()]
    assert data["id"] in ids


def test_repaso_hoy_excluye_conceptos_con_revision_futura(client_abierto, asignatura_id):
    data = _crear_concepto(client_abierto, asignatura_id, "Ya repasado")
    client_abierto.post(f"/conceptos/{data['id']}/subir")  # proxima_revision pasa a hoy+3
    r = client_abierto.get("/repaso-hoy")
    ids = [c["id"] for c in r.get_json()]
    assert data["id"] not in ids
