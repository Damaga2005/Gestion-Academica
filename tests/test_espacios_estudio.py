"""
Tests de "Espacios de Estudio Inteligentes": un espacio nace de una tarea/evento
del calendario, agrupa REFERENCIAS a Documento (nunca copias) en secciones, con
checklist de objetivos y progreso de lectura propio de la asociación.
"""

import io

import pytest


def _pdf_bytes(nombre="x.pdf"):
    return (io.BytesIO(b"%PDF-1.4 contenido"), nombre)


@pytest.fixture
def asignatura_id(client_abierto):
    return client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]


@pytest.fixture
def documento_id(client_abierto, asignatura_id):
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/examenes/documentos",
        data={"archivos": [_pdf_bytes("parcial_2023.pdf")]},
        content_type="multipart/form-data",
    )
    return r.get_json()[0]["id"]


@pytest.fixture
def tarea_examen_id(client_abierto, asignatura_id):
    r = client_abierto.post("/tareas", json={
        "titulo": "Parcial Diseño Digital",
        "fecha": "2026-11-15",
        "tipo": "examen_parcial",
        "asignatura_id": asignatura_id,
    })
    assert r.status_code == 201
    return r.get_json()["id"]


@pytest.fixture
def espacio_id(client_abierto, tarea_examen_id):
    r = client_abierto.post("/espacios-estudio", json={"tarea_evento_id": tarea_examen_id})
    assert r.status_code == 201
    return r.get_json()["id"]


# --- Creación del espacio ---

def test_crear_espacio_desde_tarea(client_abierto, tarea_examen_id):
    r = client_abierto.post("/espacios-estudio", json={"tarea_evento_id": tarea_examen_id})
    assert r.status_code == 201
    data = r.get_json()
    assert data["nombre"] == "Parcial Diseño Digital"
    assert data["fecha"] == "2026-11-15"
    assert data["tarea_evento_id"] == tarea_examen_id
    assert data["total_documentos"] == 0
    assert data["progreso_pct"] == 0


def test_crear_espacio_es_idempotente(client_abierto, tarea_examen_id):
    r1 = client_abierto.post("/espacios-estudio", json={"tarea_evento_id": tarea_examen_id})
    r2 = client_abierto.post("/espacios-estudio", json={"tarea_evento_id": tarea_examen_id})
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.get_json()["id"] == r2.get_json()["id"]


def test_crear_espacio_tarea_inexistente_404(client_abierto):
    r = client_abierto.post("/espacios-estudio", json={"tarea_evento_id": 999999})
    assert r.status_code == 404


def test_obtener_espacio_de_tarea(client_abierto, tarea_examen_id, espacio_id):
    r = client_abierto.get(f"/tareas/{tarea_examen_id}/espacio-estudio")
    assert r.status_code == 200
    assert r.get_json()["id"] == espacio_id


def test_tarea_sin_espacio_devuelve_404(client_abierto, asignatura_id):
    r = client_abierto.post("/tareas", json={
        "titulo": "Tarea suelta", "fecha": "2026-12-01", "tipo": "tarea_general",
    })
    tarea_id = r.get_json()["id"]
    r2 = client_abierto.get(f"/tareas/{tarea_id}/espacio-estudio")
    assert r2.status_code == 404


# --- Referencias a documentos: nunca duplican ni mueven ---

def test_anadir_documento_referencia_sin_duplicar(client_abierto, espacio_id, documento_id):
    r = client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "examenes_anteriores",
    })
    assert r.status_code == 201
    ref = r.get_json()
    assert ref["documento_id"] == documento_id
    assert ref["seccion"] == "examenes_anteriores"
    assert ref["leido"] is False
    assert ref["destacado"] is False

    # El documento original sigue existiendo tal cual, solo una referencia nueva.
    doc = client_abierto.get(f"/documentos/{documento_id}").get_json()
    assert doc["id"] == documento_id


def test_no_se_puede_referenciar_dos_veces_el_mismo_documento(client_abierto, espacio_id, documento_id):
    client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "teoria",
    })
    r = client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "ejercicios",
    })
    assert r.status_code == 409


def test_seccion_invalida_rechazada(client_abierto, espacio_id, documento_id):
    r = client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "no_existe",
    })
    assert r.status_code == 400


def test_marcar_leido_y_destacado(client_abierto, espacio_id, documento_id):
    ref = client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "teoria",
    }).get_json()

    r = client_abierto.put(f"/espacios-estudio/documentos/{ref['id']}", json={"leido": True, "destacado": True})
    assert r.status_code == 200
    actualizado = r.get_json()
    assert actualizado["leido"] is True
    assert actualizado["destacado"] is True

    espacio = client_abierto.get(f"/espacios-estudio/{espacio_id}").get_json()
    assert espacio["total_documentos"] == 1
    assert espacio["documentos_leidos"] == 1
    assert espacio["documentos_pendientes"] == 0
    assert espacio["progreso_pct"] == 100


def test_cambiar_seccion_de_una_referencia(client_abierto, espacio_id, documento_id):
    ref = client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "teoria",
    }).get_json()
    r = client_abierto.put(f"/espacios-estudio/documentos/{ref['id']}", json={"seccion": "ejercicios"})
    assert r.status_code == 200
    assert r.get_json()["seccion"] == "ejercicios"


def test_quitar_referencia_no_borra_el_documento(client_abierto, espacio_id, documento_id):
    ref = client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "teoria",
    }).get_json()

    r = client_abierto.delete(f"/espacios-estudio/documentos/{ref['id']}")
    assert r.status_code == 204

    doc = client_abierto.get(f"/documentos/{documento_id}").get_json()
    assert doc["id"] == documento_id  # el documento real sigue existiendo


def test_borrar_espacio_no_borra_documentos(client_abierto, espacio_id, documento_id):
    client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "teoria",
    })

    r = client_abierto.delete(f"/espacios-estudio/{espacio_id}")
    assert r.status_code == 204

    assert client_abierto.get(f"/espacios-estudio/{espacio_id}").status_code == 404
    doc = client_abierto.get(f"/documentos/{documento_id}").get_json()
    assert doc["id"] == documento_id


# --- Buscador de documentos ---

def test_buscar_documentos_excluye_ya_referenciados(client_abierto, espacio_id, documento_id):
    r = client_abierto.get(f"/espacios-estudio/buscar-documentos?excluir_espacio_id={espacio_id}")
    ids = [d["id"] for d in r.get_json()]
    assert documento_id in ids

    client_abierto.post(f"/espacios-estudio/{espacio_id}/documentos", json={
        "documento_id": documento_id, "seccion": "examenes_anteriores",
    })
    r2 = client_abierto.get(f"/espacios-estudio/buscar-documentos?excluir_espacio_id={espacio_id}")
    ids2 = [d["id"] for d in r2.get_json()]
    assert documento_id not in ids2


def test_buscar_documentos_por_nombre(client_abierto, espacio_id, documento_id):
    r = client_abierto.get("/espacios-estudio/buscar-documentos?q=parcial_2023")
    ids = [d["id"] for d in r.get_json()]
    assert documento_id in ids

    r2 = client_abierto.get("/espacios-estudio/buscar-documentos?q=xyznoexiste")
    assert r2.get_json() == []


# --- Checklist de objetivos ---

def test_checklist_objetivos_crud(client_abierto, espacio_id):
    r = client_abierto.post(f"/espacios-estudio/{espacio_id}/objetivos", json={"texto": "Leer Tema 4"})
    assert r.status_code == 201
    objetivo = r.get_json()
    assert objetivo["texto"] == "Leer Tema 4"
    assert objetivo["completada"] is False

    r2 = client_abierto.put(f"/espacios-estudio/objetivos/{objetivo['id']}", json={"completada": True})
    assert r2.get_json()["completada"] is True

    espacio = client_abierto.get(f"/espacios-estudio/{espacio_id}").get_json()
    assert espacio["total_objetivos"] == 1
    assert espacio["objetivos_completados"] == 1

    r3 = client_abierto.delete(f"/espacios-estudio/objetivos/{objetivo['id']}")
    assert r3.status_code == 204


def test_objetivo_texto_vacio_rechazado(client_abierto, espacio_id):
    r = client_abierto.post(f"/espacios-estudio/{espacio_id}/objetivos", json={"texto": "   "})
    assert r.status_code == 400


# --- Listado ---

def test_listar_espacios(client_abierto, espacio_id):
    r = client_abierto.get("/espacios-estudio")
    assert r.status_code == 200
    ids = [e["id"] for e in r.get_json()]
    assert espacio_id in ids
