import io
import os
import sqlite3
import zipfile

import pytest

from models import Asignatura


def _zip_bytes(entries):
    """entries: lista de (nombre, bytes) a meter en un .zip en memoria."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in entries:
            zf.writestr(nombre, contenido)
    buffer.seek(0)
    return buffer.read()


def _sqlite_valido_bytes(tmp_path, incluir_tablas_obligatorias=True):
    ruta = tmp_path / "valido.db"
    conexion = sqlite3.connect(str(ruta))
    if incluir_tablas_obligatorias:
        conexion.execute("CREATE TABLE anio (id INTEGER PRIMARY KEY)")
        conexion.execute("CREATE TABLE asignatura (id INTEGER PRIMARY KEY)")
        conexion.execute("CREATE TABLE documento (id INTEGER PRIMARY KEY)")
    else:
        conexion.execute("CREATE TABLE otra_cosa (id INTEGER PRIMARY KEY)")
    conexion.commit()
    conexion.close()
    return ruta.read_bytes()


def test_exportar_importar_round_trip(client_abierto):
    total_antes = None
    with client_abierto.application.app_context():
        total_antes = Asignatura.query.count()
    assert total_antes and total_antes > 0

    r = client_abierto.get("/backup/exportar")
    assert r.status_code == 200
    zip_bytes = r.data

    r = client_abierto.post(
        "/backup/importar",
        data={"backup": (io.BytesIO(zip_bytes), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["requiere_reinicio"] is True

    with client_abierto.application.app_context():
        assert Asignatura.query.count() == total_antes


def test_falta_academico_db_es_rechazado(client_abierto):
    zip_bytes = _zip_bytes([("otro.txt", b"nada")])
    r = client_abierto.post(
        "/backup/importar",
        data={"backup": (io.BytesIO(zip_bytes), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "academico.db" in r.get_json()["error"]


def test_zip_slip_es_rechazado(client_abierto, tmp_path):
    db_valida = _sqlite_valido_bytes(tmp_path)
    zip_bytes = _zip_bytes([
        ("academico.db", db_valida),
        ("../../evil.txt", b"pwned"),
    ])
    r = client_abierto.post(
        "/backup/importar",
        data={"backup": (io.BytesIO(zip_bytes), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "Zip Slip" in r.get_json()["error"] or "ruta" in r.get_json()["error"].lower()

    with client_abierto.application.app_context():
        assert Asignatura.query.count() > 0  # datos originales intactos


def test_zip_bomb_es_rechazado(client_abierto):
    # 2 MB de ceros comprime a un tamaño ínfimo: ratio de compresión disparado,
    # sin necesidad de generar un fixture de varios GB.
    contenido_enorme = b"\x00" * (2 * 1024 * 1024)
    zip_bytes = _zip_bytes([("academico.db", contenido_enorme)])
    r = client_abierto.post(
        "/backup/importar",
        data={"backup": (io.BytesIO(zip_bytes), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "bomb" in r.get_json()["error"].lower() or "grande" in r.get_json()["error"].lower()


def test_sqlite_corrupta_es_rechazada(client_abierto):
    zip_bytes = _zip_bytes([("academico.db", b"esto no es una base de datos sqlite")])
    r = client_abierto.post(
        "/backup/importar",
        data={"backup": (io.BytesIO(zip_bytes), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400

    with client_abierto.application.app_context():
        assert Asignatura.query.count() > 0  # datos originales intactos


def test_sqlite_sin_tablas_obligatorias_es_rechazada(client_abierto, tmp_path):
    db_incompleta = _sqlite_valido_bytes(tmp_path, incluir_tablas_obligatorias=False)
    zip_bytes = _zip_bytes([("academico.db", db_incompleta)])
    r = client_abierto.post(
        "/backup/importar",
        data={"backup": (io.BytesIO(zip_bytes), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "tabla" in r.get_json()["error"].lower()


def test_no_es_zip_es_rechazado(client_abierto):
    r = client_abierto.post(
        "/backup/importar",
        data={"backup": (io.BytesIO(b"no soy un zip"), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400


def test_rollback_si_falla_la_migracion(client_abierto, monkeypatch):
    """Si algo falla DESPUÉS de sustituir la BD (aquí: la migración), se debe
    revertir por completo al snapshot previo, sin dejar el estado a medias."""
    with client_abierto.application.app_context():
        total_antes = Asignatura.query.count()

    r = client_abierto.get("/backup/exportar")
    zip_bytes = r.data  # backup real y válido de los datos actuales

    def _migracion_rota(*args, **kwargs):
        raise RuntimeError("fallo simulado en la migración")

    monkeypatch.setattr("flask_migrate.upgrade", _migracion_rota)

    r = client_abierto.post(
        "/backup/importar",
        data={"backup": (io.BytesIO(zip_bytes), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "revertido" in r.get_json()["error"].lower()

    with client_abierto.application.app_context():
        assert Asignatura.query.count() == total_antes


def test_listar_backups_automaticos_sin_carpeta_devuelve_vacio(client_abierto, tmp_path, monkeypatch):
    monkeypatch.setattr("routes.backup.DATA_DIR", str(tmp_path))
    assert client_abierto.get("/backup/automaticos").get_json() == []


def test_listar_backups_automaticos_los_devuelve_mas_reciente_primero(client_abierto, tmp_path, monkeypatch):
    monkeypatch.setattr("routes.backup.DATA_DIR", str(tmp_path))
    carpeta = tmp_path / "backups"
    carpeta.mkdir()
    (carpeta / "auto_2026-09-01_100000.zip").write_bytes(b"x" * 1024)
    (carpeta / "auto_2026-09-02_100000.zip").write_bytes(b"x" * 2048)
    (carpeta / "otro_archivo.txt").write_bytes(b"no cuenta")

    backups = client_abierto.get("/backup/automaticos").get_json()
    assert [b["nombre"] for b in backups] == ["auto_2026-09-02_100000.zip", "auto_2026-09-01_100000.zip"]
    assert backups[0]["tamano_bytes"] == 2048


def test_descargar_backup_automatico(client_abierto, tmp_path, monkeypatch):
    monkeypatch.setattr("routes.backup.DATA_DIR", str(tmp_path))
    carpeta = tmp_path / "backups"
    carpeta.mkdir()
    (carpeta / "auto_2026-09-01_100000.zip").write_bytes(b"contenido real")

    r = client_abierto.get("/backup/automaticos/auto_2026-09-01_100000.zip")
    assert r.status_code == 200
    assert r.data == b"contenido real"


def test_descargar_backup_automatico_inexistente_404(client_abierto, tmp_path, monkeypatch):
    monkeypatch.setattr("routes.backup.DATA_DIR", str(tmp_path))
    r = client_abierto.get("/backup/automaticos/auto_2026-01-01_000000.zip")
    assert r.status_code == 404


def test_descargar_backup_automatico_rechaza_path_traversal(client_abierto, tmp_path, monkeypatch):
    monkeypatch.setattr("routes.backup.DATA_DIR", str(tmp_path))
    # fuera de backups/: si el nombre no encaja con el patrón auto_YYYY-MM-DD_HHMMSS.zip,
    # ni se llega a construir la ruta.
    r = client_abierto.get("/backup/automaticos/..%2f..%2facademico.db")
    assert r.status_code == 404


def test_restore_tmp_se_limpia_tras_cada_intento(client_abierto, tmp_path):
    zip_bytes = _zip_bytes([("otro.txt", b"nada")])
    client_abierto.post(
        "/backup/importar",
        data={"backup": (io.BytesIO(zip_bytes), "backup.zip")},
        content_type="multipart/form-data",
    )
    db_path = client_abierto.application.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "", 1)
    restore_tmp = os.path.join(os.path.dirname(db_path), ".restore_tmp")
    if os.path.isdir(restore_tmp):
        assert os.listdir(restore_tmp) == []
