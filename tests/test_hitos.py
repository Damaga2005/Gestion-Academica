"""
Tests de Hitos (certificaciones/proyectos propios, spec punto 8): routes/hitos.py.
Sin test previo pese a tener CRUD completo + validación de estado y de fecha.
"""


def _crear_hito(client, nombre="Hito de prueba", **extra):
    r = client.post("/hitos", json={"nombre": nombre, **extra})
    assert r.status_code == 201
    return r.get_json()


def test_crear_hito_nace_pendiente_sin_fecha(client_abierto):
    data = _crear_hito(client_abierto)
    assert data["estado"] == "pendiente"
    assert data["fecha"] is None


def test_crear_hito_sin_nombre_falla(client_abierto):
    assert client_abierto.post("/hitos", json={}).status_code == 400


def test_crear_hito_con_fecha_y_estado(client_abierto):
    data = _crear_hito(client_abierto, fecha="2026-12-01", estado="en_progreso")
    assert data["fecha"] == "2026-12-01"
    assert data["estado"] == "en_progreso"


def test_crear_hito_fecha_formato_invalido_falla(client_abierto):
    r = client_abierto.post("/hitos", json={"nombre": "X", "fecha": "01-12-2026"})
    assert r.status_code == 400


def test_crear_hito_estado_invalido_falla(client_abierto):
    r = client_abierto.post("/hitos", json={"nombre": "X", "estado": "no_existe"})
    assert r.status_code == 400


def test_orden_por_defecto_es_incremental(client_abierto):
    primero = _crear_hito(client_abierto, "Primero")
    segundo = _crear_hito(client_abierto, "Segundo")
    assert segundo["orden"] > primero["orden"]


def test_listar_hitos_respeta_orden(client_abierto):
    a = _crear_hito(client_abierto, "A", orden=2)
    b = _crear_hito(client_abierto, "B", orden=1)
    ids_en_orden = [h["id"] for h in client_abierto.get("/hitos").get_json()]
    assert ids_en_orden.index(b["id"]) < ids_en_orden.index(a["id"])


def test_actualizar_hito_cambia_estado(client_abierto):
    data = _crear_hito(client_abierto)
    r = client_abierto.put(f"/hitos/{data['id']}", json={"estado": "hecho"})
    assert r.get_json()["estado"] == "hecho"


def test_actualizar_hito_estado_invalido_falla(client_abierto):
    data = _crear_hito(client_abierto)
    r = client_abierto.put(f"/hitos/{data['id']}", json={"estado": "raro"})
    assert r.status_code == 400


def test_actualizar_hito_inexistente_404(client_abierto):
    assert client_abierto.put("/hitos/999999", json={"nombre": "x"}).status_code == 404


def test_borrar_hito(client_abierto):
    data = _crear_hito(client_abierto)
    assert client_abierto.delete(f"/hitos/{data['id']}").status_code == 204
    assert client_abierto.put(f"/hitos/{data['id']}", json={"nombre": "x"}).status_code == 404
