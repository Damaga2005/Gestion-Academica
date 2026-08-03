"""
Tests de la API de anotaciones del visor de PDF (resaltar / subrayar / tachar /
nota): alta, listado, edición, borrado, validación de la geometría normalizada y
borrado en cascada al eliminar el documento.
"""

import io

import pytest


@pytest.fixture
def documento_id(client_abierto):
    asignatura_id = client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/teoria/documentos",
        data={"archivos": [(io.BytesIO(b"%PDF-1.4 contenido"), "apuntes.pdf")]},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    return r.get_json()[0]["id"]


RECTS = [[0.1, 0.2, 0.5, 0.02]]


def _crear(client, documento_id, **extra):
    cuerpo = {"numero_pagina": 3, "tipo": "resaltado", "color": "#ffd400",
              "texto": "un párrafo", "rects": RECTS}
    cuerpo.update(extra)
    return client.post(f"/documentos/{documento_id}/anotaciones", json=cuerpo)


# --- Alta y listado ---

def test_crear_y_listar(client_abierto, documento_id):
    r = _crear(client_abierto, documento_id)
    assert r.status_code == 201
    creada = r.get_json()
    assert creada["numero_pagina"] == 3
    assert creada["tipo"] == "resaltado"
    assert creada["rects"] == RECTS

    listado = client_abierto.get(f"/documentos/{documento_id}/anotaciones").get_json()
    assert [a["id"] for a in listado] == [creada["id"]]


def test_listado_vacio(client_abierto, documento_id):
    r = client_abierto.get(f"/documentos/{documento_id}/anotaciones")
    assert r.status_code == 200
    assert r.get_json() == []


@pytest.mark.parametrize("tipo", ["resaltado", "subrayado", "tachado", "nota"])
def test_tipos_admitidos(client_abierto, documento_id, tipo):
    assert _crear(client_abierto, documento_id, tipo=tipo).status_code == 201


def test_tipo_invalido_rechazado(client_abierto, documento_id):
    assert _crear(client_abierto, documento_id, tipo="garabato").status_code == 400


def test_color_fuera_de_la_paleta_rechazado(client_abierto, documento_id):
    """El color acaba en un style del DOM: solo se aceptan los de la paleta."""
    assert _crear(client_abierto, documento_id, color="url(javascript:0)").status_code == 400


def test_documento_inexistente(client_abierto):
    assert client_abierto.get("/documentos/99999/anotaciones").status_code == 404


# --- Validación de la geometría ---

def test_rects_obligatorios(client_abierto, documento_id):
    assert _crear(client_abierto, documento_id, rects=[]).status_code == 400


def test_rect_mal_formado(client_abierto, documento_id):
    assert _crear(client_abierto, documento_id, rects=[[0.1, 0.2]]).status_code == 400


def test_rect_no_numerico(client_abierto, documento_id):
    assert _crear(client_abierto, documento_id, rects=[["a", 0.2, 0.3, 0.4]]).status_code == 400


def test_rect_degenerado_se_descarta(client_abierto, documento_id):
    """Ancho o alto 0 no aporta nada; si no queda ninguno válido, es un 400."""
    assert _crear(client_abierto, documento_id, rects=[[0.1, 0.2, 0, 0.05]]).status_code == 400


def test_rect_se_recorta_a_la_pagina(client_abierto, documento_id):
    """Un redondeo del navegador puede dar 1.0000001; se recorta, no se rechaza."""
    r = _crear(client_abierto, documento_id, rects=[[0.9, 0.5, 0.4, 0.02]])
    assert r.status_code == 201
    x, y, ancho, alto = r.get_json()["rects"][0]
    assert x == pytest.approx(0.9)
    assert ancho == pytest.approx(0.1)


def test_pagina_invalida(client_abierto, documento_id):
    assert _crear(client_abierto, documento_id, numero_pagina=0).status_code == 400


# --- Edición y borrado ---

def test_actualizar_color_y_comentario(client_abierto, documento_id):
    anotacion_id = _crear(client_abierto, documento_id).get_json()["id"]
    r = client_abierto.patch(
        f"/anotaciones/{anotacion_id}",
        json={"color": "#60a5fa", "comentario": "revisar esto"},
    )
    assert r.status_code == 200
    assert r.get_json()["color"] == "#60a5fa"
    assert r.get_json()["comentario"] == "revisar esto"


def test_actualizar_color_invalido(client_abierto, documento_id):
    anotacion_id = _crear(client_abierto, documento_id).get_json()["id"]
    assert client_abierto.patch(f"/anotaciones/{anotacion_id}", json={"color": "#000000"}).status_code == 400


def test_borrar(client_abierto, documento_id):
    anotacion_id = _crear(client_abierto, documento_id).get_json()["id"]
    assert client_abierto.delete(f"/anotaciones/{anotacion_id}").status_code == 204
    assert client_abierto.get(f"/documentos/{documento_id}/anotaciones").get_json() == []


def test_borrar_documento_arrastra_sus_anotaciones(client_abierto, documento_id):
    anotacion_id = _crear(client_abierto, documento_id).get_json()["id"]
    assert client_abierto.delete(f"/documentos/{documento_id}").status_code == 204
    assert client_abierto.delete(f"/anotaciones/{anotacion_id}").status_code == 404
