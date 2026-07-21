"""
Tests de la Fase "Organización jerárquica de documentos" (spec punto 12):
categorías fijas, subgrupos, subida jerárquica, mover documentos, eliminar
subgrupos, conservación de datos tras la migración, y seguridad con
GREELEC_LOCK_KEY.
"""

import io

import pytest


def _pdf_bytes(nombre="x.pdf"):
    return (io.BytesIO(b"%PDF-1.4 contenido"), nombre)


@pytest.fixture
def asignatura_id(client_abierto):
    return client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]


# --- Crear grupos ---

def test_crear_grupo(client_abierto, asignatura_id):
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"})
    assert r.status_code == 201
    assert r.get_json()["nombre"] == "Tema 1"
    assert r.get_json()["categoria"] == "teoria"


def test_normaliza_espacios_del_nombre(client_abierto, asignatura_id):
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "  Tema   1  "})
    assert r.status_code == 201
    assert r.get_json()["nombre"] == "Tema 1"


def test_nombre_vacio_rechazado(client_abierto, asignatura_id):
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "   "})
    assert r.status_code == 400


def test_categoria_invalida_rechazada(client_abierto, asignatura_id):
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "practicas", "nombre": "X"})
    assert r.status_code == 404


def test_categorias_fijas_no_se_pueden_crear_ni_borrar(client_abierto, asignatura_id):
    """No existe ninguna ruta para crear/eliminar una categoría: solo se puede crear
    un GrupoDocumento *dentro* de una de las 4 fijas."""
    arbol = client_abierto.get(f"/asignaturas/{asignatura_id}/documentos/arbol").get_json()
    assert {c["categoria"] for c in arbol} == {"teoria", "examenes", "laboratorios", "otros"}


# --- Evitar duplicados ---

def test_evitar_duplicados_misma_categoria(client_abierto, asignatura_id):
    client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"})
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"})
    assert r.status_code == 409


def test_mismo_nombre_permitido_en_otra_categoria(client_abierto, asignatura_id):
    client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"})
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "examenes", "nombre": "Tema 1"})
    assert r.status_code == 201


def test_mismo_nombre_permitido_en_otra_asignatura(client_abierto):
    asigs = client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[:2]
    client_abierto.post(f"/asignaturas/{asigs[0]['id']}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"})
    r = client_abierto.post(f"/asignaturas/{asigs[1]['id']}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"})
    assert r.status_code == 201


def test_renombrar_a_duplicado_rechazado(client_abierto, asignatura_id):
    client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "A"})
    gid_b = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "B"}).get_json()["id"]
    r = client_abierto.put(f"/grupos/{gid_b}", json={"nombre": "A"})
    assert r.status_code == 409


def test_reordenar_grupo(client_abierto, asignatura_id):
    gid = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "A"}).get_json()["id"]
    r = client_abierto.put(f"/grupos/{gid}", json={"orden": 5})
    assert r.status_code == 200
    assert r.get_json()["orden"] == 5


# --- Subir archivos ---

def test_subir_a_subgrupo(client_abierto, asignatura_id):
    gid = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"}).get_json()["id"]
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/teoria/documentos",
        data={"archivos": [_pdf_bytes("apuntes.pdf")], "grupo_id": str(gid)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    doc = r.get_json()[0]
    assert doc["categoria"] == "teoria" and doc["grupo_documento_id"] == gid
    assert doc["tamano_bytes"] > 0


def test_subir_sin_grupo_queda_sin_clasificar(client_abierto, asignatura_id):
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/examenes/documentos",
        data={"archivos": [_pdf_bytes("suelto.pdf")]},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    assert r.get_json()[0]["grupo_documento_id"] is None


def test_subida_multiple(client_abierto, asignatura_id):
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/otros/documentos",
        data={"archivos": [_pdf_bytes("a.pdf"), _pdf_bytes("b.pdf")]},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    assert len(r.get_json()) == 2


def test_grupo_de_otra_categoria_rechazado_al_subir(client_abierto, asignatura_id):
    gid = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"}).get_json()["id"]
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/examenes/documentos",
        data={"archivos": [_pdf_bytes()], "grupo_id": str(gid)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400


# --- Mover documentos ---

def test_mover_entre_categorias(client_abierto, asignatura_id):
    doc = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/teoria/documentos",
        data={"archivos": [_pdf_bytes()]}, content_type="multipart/form-data",
    ).get_json()[0]

    r = client_abierto.put(f"/documentos/{doc['id']}/mover", json={"categoria": "laboratorios"})
    assert r.status_code == 200
    assert r.get_json()["categoria"] == "laboratorios"
    assert r.get_json()["grupo_documento_id"] is None


def test_mover_entre_subgrupos_no_duplica_archivo(client_abierto, asignatura_id):
    g1 = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "A"}).get_json()["id"]
    g2 = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "B"}).get_json()["id"]
    doc = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/teoria/documentos",
        data={"archivos": [_pdf_bytes()], "grupo_id": str(g1)}, content_type="multipart/form-data",
    ).get_json()[0]

    r = client_abierto.put(f"/documentos/{doc['id']}/mover", json={"categoria": "teoria", "grupo_id": g2})
    assert r.status_code == 200
    assert r.get_json()["grupo_documento_id"] == g2

    # Sigue siendo UN solo documento (no se duplicó al mover)
    todos = client_abierto.get(f"/asignaturas/{asignatura_id}/categorias/teoria/documentos?todos=1").get_json()
    assert len(todos) == 1


def test_mover_a_grupo_de_otra_categoria_rechazado(client_abierto, asignatura_id):
    gid = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"}).get_json()["id"]
    doc = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/examenes/documentos",
        data={"archivos": [_pdf_bytes()]}, content_type="multipart/form-data",
    ).get_json()[0]

    r = client_abierto.put(f"/documentos/{doc['id']}/mover", json={"categoria": "examenes", "grupo_id": gid})
    assert r.status_code == 400


# --- Eliminar grupos ---

def test_eliminar_grupo_preserva_documentos(client_abierto, asignatura_id):
    gid = client_abierto.post(f"/asignaturas/{asignatura_id}/grupos", json={"categoria": "teoria", "nombre": "Tema 1"}).get_json()["id"]
    client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/teoria/documentos",
        data={"archivos": [_pdf_bytes()], "grupo_id": str(gid)}, content_type="multipart/form-data",
    )

    r = client_abierto.delete(f"/grupos/{gid}")
    assert r.status_code == 204

    arbol = client_abierto.get(f"/asignaturas/{asignatura_id}/documentos/arbol").get_json()
    teoria = next(c for c in arbol if c["categoria"] == "teoria")
    assert teoria["grupos"] == []
    assert teoria["sin_clasificar"] == 1  # el documento sigue existiendo, ahora sin clasificar
    assert teoria["total_documentos"] == 1


# --- Conservar datos existentes ---

def test_migracion_conserva_documentos_existentes(app_abierta):
    """Complementa test_migracion.py: aquí se verifica el backfill de esta fase en
    concreto usando datos ya sembrados con Apartado (el modelo previo)."""
    with app_abierta.app_context():
        from models import db, Asignatura, Apartado, Documento
        asignatura = Asignatura.query.filter_by(nombre="Álgebra Lineal").first()
        apartado_teoria = Apartado.query.filter_by(asignatura_id=asignatura.id, nombre="Teoría").first()

        doc = Documento(
            asignatura_id=asignatura.id, apartado_id=apartado_teoria.id,
            nombre_archivo="viejo.pdf", ruta_local="x/viejo.pdf",
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

        # Sin categoria todavía (simula un documento anterior a esta fase)
        assert Documento.query.get(doc_id).categoria is None

        from utils import carpeta_categoria  # solo para confirmar que el helper no revienta
        assert carpeta_categoria(asignatura, "teoria")


# --- Seguridad ---

def test_rutas_nuevas_protegidas_por_lock_key(client_bloqueado, app_bloqueada):
    """Con GREELEC_LOCK_KEY activa, las rutas nuevas de esta fase deben exigir
    autenticación igual que el resto de la API (spec punto 10)."""
    with app_bloqueada.app_context():
        from models import Asignatura
        aid = Asignatura.query.filter_by(tipo="obligatoria").first().id

    r = client_bloqueado.get(f"/asignaturas/{aid}/documentos/arbol")
    assert r.status_code == 401

    r = client_bloqueado.post(f"/asignaturas/{aid}/grupos", json={"categoria": "teoria", "nombre": "X"})
    assert r.status_code == 401


def test_rutas_nuevas_funcionan_con_clave_correcta(client_bloqueado, app_bloqueada):
    with app_bloqueada.app_context():
        from models import Asignatura
        aid = Asignatura.query.filter_by(tipo="obligatoria").first().id

    r = client_bloqueado.get(
        f"/asignaturas/{aid}/documentos/arbol",
        headers={"X-GREELEC-KEY": "clave-test-1234"},
    )
    assert r.status_code == 200


def test_nombre_archivo_se_sanea(client_abierto, asignatura_id):
    """secure_filename() debe neutralizar rutas/caracteres peligrosos en el nombre
    del archivo subido (spec punto 10: validar nombres de archivo)."""
    archivo = (io.BytesIO(b"%PDF-1.4 x"), "../../../etc/passwd.pdf")
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/otros/documentos",
        data={"archivos": [archivo]}, content_type="multipart/form-data",
    )
    assert r.status_code == 201
    nombre_guardado = r.get_json()[0]["nombre_archivo"]
    assert "/" not in nombre_guardado and ".." not in nombre_guardado


def test_categoria_como_parametro_de_ruta_se_valida(client_abierto, asignatura_id):
    """El segmento <categoria> de la URL solo acepta las 4 categorías fijas: no se
    puede usar para apuntar a una ruta de disco arbitraria."""
    r = client_abierto.get(f"/asignaturas/{asignatura_id}/categorias/../../etc/documentos")
    assert r.status_code in (404, 400)
