"""
Tests de la Fase de seguridad de documentos: resolución de rutas, extensiones,
firmas de ejecutable, tamaño/cantidad máximos, subida transaccional y auditoría
del nombre original.
"""

import io
import os

import pytest

from utils import ruta_absoluta


def _archivo(nombre, contenido=b"contenido de prueba"):
    return (io.BytesIO(contenido), nombre)


@pytest.fixture
def asignatura_id(client_abierto):
    return client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]


def _subir(client, asignatura_id, archivos, categoria="otros"):
    return client.post(
        f"/asignaturas/{asignatura_id}/categorias/{categoria}/documentos",
        data={"archivos": archivos},
        content_type="multipart/form-data",
    )


# --- ruta_absoluta: contención de path traversal ---

def test_ruta_absoluta_rechaza_escape_del_directorio(client_abierto):
    with client_abierto.application.app_context():
        with pytest.raises(Exception):
            ruta_absoluta("../../../../windows/win.ini")


def test_ruta_absoluta_acepta_ruta_normal(client_abierto):
    with client_abierto.application.app_context():
        resultado = ruta_absoluta("1_algo/archivo.pdf")
        assert resultado.endswith(os.path.join("1_algo", "archivo.pdf"))


# --- Extensiones ---

def test_extension_no_permitida_rechazada(client_abierto, asignatura_id):
    r = _subir(client_abierto, asignatura_id, [_archivo("virus.exe", b"MZ" + b"\x00" * 30)])
    assert r.status_code == 400


def test_extension_permitida_aceptada(client_abierto, asignatura_id):
    r = _subir(client_abierto, asignatura_id, [_archivo("apuntes.pdf", b"%PDF-1.4 contenido real")])
    assert r.status_code == 201


def test_doble_extension_con_varios_puntos_valida_se_acepta(client_abierto, asignatura_id):
    """'tema.1.resumen.pdf' es un nombre legítimo (varios puntos): solo importa que
    la extensión FINAL esté permitida."""
    r = _subir(client_abierto, asignatura_id, [_archivo("tema.1.resumen.pdf", b"%PDF-1.4 contenido")])
    assert r.status_code == 201
    assert r.get_json()[0]["nombre_archivo"] == "tema.1.resumen.pdf"


def test_doble_extension_ejecutable_disfrazado_rechazada(client_abierto, asignatura_id):
    """'informe.pdf.exe': la extensión final es 'exe', no está permitida."""
    r = _subir(client_abierto, asignatura_id, [_archivo("informe.pdf.exe", b"contenido cualquiera")])
    assert r.status_code == 400


def test_pdf_con_firma_de_ejecutable_rechazado(client_abierto, asignatura_id):
    """Un archivo con extensión .pdf pero que empieza por la firma MZ (ejecutable
    Windows) debe rechazarse por el contenido, no por la extensión."""
    r = _subir(client_abierto, asignatura_id, [_archivo("informe.pdf", b"MZ" + b"\x90" * 60)])
    assert r.status_code == 400


# --- Tamaño y cantidad ---

def test_archivo_demasiado_grande_rechazado(client_abierto, asignatura_id, monkeypatch):
    monkeypatch.setitem(client_abierto.application.config, "DOCUMENTO_MAX_BYTES", 10)
    r = _subir(client_abierto, asignatura_id, [_archivo("grande.pdf", b"%PDF-1.4" + b"0" * 100)])
    assert r.status_code == 400


def test_mas_de_treinta_archivos_rechazado(client_abierto, asignatura_id, monkeypatch):
    monkeypatch.setitem(client_abierto.application.config, "DOCUMENTO_MAX_ARCHIVOS_POR_SUBIDA", 3)
    archivos = [_archivo(f"a{i}.pdf", b"%PDF-1.4 x") for i in range(4)]
    r = _subir(client_abierto, asignatura_id, archivos)
    assert r.status_code == 400


# --- ZIP como documento: se guarda, nunca se extrae ---

def test_zip_como_documento_se_guarda_sin_extraer(client_abierto, asignatura_id, tmp_path):
    r = _subir(client_abierto, asignatura_id, [_archivo("material.zip", b"PK\x03\x04 no es un zip real completo")])
    assert r.status_code == 201
    assert r.get_json()[0]["nombre_archivo"] == "material.zip"


# --- Subida transaccional / sin huérfanos ---

def test_lote_con_un_archivo_invalido_no_deja_huerfanos(client_abierto, asignatura_id):
    documentos_dir = client_abierto.application.config["DOCUMENTOS_DIR"]
    archivos_antes = sum(len(f) for _, _, f in os.walk(documentos_dir))

    r = _subir(client_abierto, asignatura_id, [
        _archivo("valido.pdf", b"%PDF-1.4 contenido"),
        _archivo("malo.exe", b"MZ" + b"\x00" * 20),
    ])
    assert r.status_code == 400

    archivos_despues = sum(len(f) for _, _, f in os.walk(documentos_dir))
    assert archivos_despues == archivos_antes  # nada quedó en disco del lote fallido

    with client_abierto.application.app_context():
        from models import Documento
        assert Documento.query.filter_by(nombre_archivo="valido.pdf").count() == 0


# --- nombre_original: auditoría, nunca usado como ruta ---

def test_nombre_original_se_guarda_para_auditoria(client_abierto, asignatura_id):
    r = _subir(client_abierto, asignatura_id, [_archivo("Mi Apunte Con Espacios.pdf", b"%PDF-1.4 x")])
    assert r.status_code == 201
    datos = r.get_json()[0]
    assert datos["nombre_original"] == "Mi Apunte Con Espacios.pdf"


def test_nombre_original_con_ruta_se_reduce_al_basename(client_abierto, asignatura_id):
    archivo = (io.BytesIO(b"%PDF-1.4 x"), "../../etc/passwd.pdf")
    r = _subir(client_abierto, asignatura_id, [archivo])
    assert r.status_code == 201
    datos = r.get_json()[0]
    assert "/" not in datos["nombre_original"] and ".." not in datos["nombre_original"]
