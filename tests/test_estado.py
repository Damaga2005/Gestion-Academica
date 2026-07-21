def _primera_asignatura_id(client):
    r = client.get("/asignaturas")
    asignaturas = r.get_json()
    assert asignaturas, "el fixture debería tener asignaturas sembradas"
    return asignaturas[0]["id"]


def test_cambio_estado_valido(client_abierto):
    asignatura_id = _primera_asignatura_id(client_abierto)
    r = client_abierto.patch(f"/api/asignaturas/{asignatura_id}/estado", json={"estado": "cursando"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["id"] == asignatura_id
    assert data["estado"] == "cursando"


def test_estado_invalido_rechazado_422(client_abierto):
    asignatura_id = _primera_asignatura_id(client_abierto)
    r = client_abierto.patch(
        f"/api/asignaturas/{asignatura_id}/estado", json={"estado": "no_existe_este_estado"}
    )
    assert r.status_code == 422
    assert "error" in r.get_json()


def test_estado_faltante_rechazado_422(client_abierto):
    asignatura_id = _primera_asignatura_id(client_abierto)
    r = client_abierto.patch(f"/api/asignaturas/{asignatura_id}/estado", json={})
    assert r.status_code == 422


def test_asignatura_inexistente_devuelve_404(client_abierto):
    r = client_abierto.patch("/api/asignaturas/999999/estado", json={"estado": "cursando"})
    assert r.status_code == 404


def test_cambio_estado_es_idempotente(client_abierto):
    asignatura_id = _primera_asignatura_id(client_abierto)

    r1 = client_abierto.patch(f"/api/asignaturas/{asignatura_id}/estado", json={"estado": "cursando"})
    r2 = client_abierto.patch(f"/api/asignaturas/{asignatura_id}/estado", json={"estado": "cursando"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.get_json()["estado"] == r2.get_json()["estado"] == "cursando"


def test_todos_los_estados_permitidos_son_validos(client_abierto):
    asignatura_id = _primera_asignatura_id(client_abierto)
    for estado in ("superada", "cursando", "pendiente", "no_superada", "no_elegida"):
        r = client_abierto.patch(f"/api/asignaturas/{asignatura_id}/estado", json={"estado": estado})
        assert r.status_code == 200, f"'{estado}' debería ser un estado válido"
        assert r.get_json()["estado"] == estado
