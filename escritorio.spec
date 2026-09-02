# -*- mode: python ; coding: utf-8 -*-
# Spec de PyInstaller para empaquetar la app como .exe de escritorio (Fase 6).
# Construir con: pyinstaller escritorio.spec --noconfirm --clean

import os

PROJECT_DIR = os.path.abspath(os.path.dirname(os.path.abspath(SPEC)))

datas = [
    (os.path.join(PROJECT_DIR, "templates"), "templates"),
    (os.path.join(PROJECT_DIR, "static"), "static"),
    # migrations/ (Fase 11): necesaria en tiempo de ejecución para que
    # flask_migrate.upgrade() pueda construir/actualizar el esquema al arrancar.
    (os.path.join(PROJECT_DIR, "migrations"), "migrations"),
]

a = Analysis(
    ["escritorio.py"],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "sqlalchemy.sql.default_comparator",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.pysqlite",
        "clr_loader",
        "winotify",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
        "alembic",
        "flask_migrate",
        "dotenv",
        # migrations/env.py se ejecuta en tiempo de ejecución vía importlib (Alembic lo
        # carga como archivo de datos, no como código fuente), así que PyInstaller no ve
        # sus imports por análisis estático: hay que declararlos aquí a mano.
        "logging.config",
        "alembic.context",
        "alembic.op",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GestionAcademicaGREELEC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_DIR, "icono.ico"),
)
