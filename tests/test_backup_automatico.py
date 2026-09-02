"""
Test del backup automático al arrancar (_backup_automatico en escritorio.py):
genera un .zip válido en DATA_DIR/backups/ y conserva solo los últimos 10, sin
tocar el flujo de arranque si algo falla (spec "qué mejorar": antes el único
backup era el export manual desde Configuración).
"""

import os
import zipfile

import escritorio


def test_backup_automatico_crea_un_zip_valido(app_abierta, tmp_path, monkeypatch):
    monkeypatch.setattr(escritorio, "DATA_DIR", str(tmp_path))

    escritorio._backup_automatico(app_abierta)

    carpeta = tmp_path / "backups"
    archivos = list(carpeta.glob("auto_*.zip"))
    assert len(archivos) == 1
    with zipfile.ZipFile(archivos[0]) as zf:
        assert "academico.db" in zf.namelist()


def test_backup_automatico_conserva_solo_los_ultimos_10(app_abierta, tmp_path, monkeypatch):
    monkeypatch.setattr(escritorio, "DATA_DIR", str(tmp_path))
    carpeta = tmp_path / "backups"
    carpeta.mkdir()
    # 12 backups "antiguos" ya existentes, con nombres ordenables por fecha
    for i in range(12):
        (carpeta / f"auto_2026-01-{i + 1:02d}_000000.zip").write_bytes(b"x")

    escritorio._backup_automatico(app_abierta)

    restantes = sorted(p.name for p in carpeta.glob("auto_*.zip"))
    assert len(restantes) == 10
    # se conservan los más recientes (por orden de nombre) + el recién creado
    assert restantes[0] == "auto_2026-01-04_000000.zip"
    assert "auto_2026-01-12_000000.zip" in restantes


def test_backup_automatico_no_repite_si_ya_hay_uno_de_hoy(app_abierta, tmp_path, monkeypatch):
    monkeypatch.setattr(escritorio, "DATA_DIR", str(tmp_path))
    from datetime import datetime
    hoy = datetime.now().strftime("%Y-%m-%d")
    carpeta = tmp_path / "backups"
    carpeta.mkdir()
    (carpeta / f"auto_{hoy}_090000.zip").write_bytes(b"ya generado hoy")

    llamadas = []
    monkeypatch.setattr("routes.backup.escribir_zip_backup", lambda destino: llamadas.append(destino))

    escritorio._backup_automatico(app_abierta)

    assert llamadas == []  # no se ha vuelto a generar
    assert len(list(carpeta.glob("auto_*.zip"))) == 1


def test_backup_automatico_no_propaga_error(app_abierta, tmp_path, monkeypatch):
    monkeypatch.setattr(escritorio, "DATA_DIR", str(tmp_path))

    def _falla(destino):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr("routes.backup.escribir_zip_backup", _falla)

    escritorio._backup_automatico(app_abierta)  # no debe lanzar
    assert list((tmp_path / "backups").glob("auto_*.zip")) == []
