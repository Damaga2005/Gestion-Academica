"""Notas rápidas: bloc de notas suelto, sin vínculo con ninguna otra entidad."""


def test_crear_y_listar_mas_recientes_primero(client_abierto):
    r1 = client_abierto.post("/notas-rapidas", json={"texto": "primera"})
    assert r1.status_code == 201
    r2 = client_abierto.post("/notas-rapidas", json={"texto": "segunda"})
    assert r2.status_code == 201

    notas = client_abierto.get("/notas-rapidas").get_json()
    assert [n["texto"] for n in notas] == ["segunda", "primera"]


def test_texto_vacio_rechazado(client_abierto):
    r = client_abierto.post("/notas-rapidas", json={"texto": "   "})
    assert r.status_code == 400


def test_borrar_nota(client_abierto):
    nota_id = client_abierto.post("/notas-rapidas", json={"texto": "temporal"}).get_json()["id"]
    r = client_abierto.delete(f"/notas-rapidas/{nota_id}")
    assert r.status_code == 204
    assert client_abierto.get("/notas-rapidas").get_json() == []
