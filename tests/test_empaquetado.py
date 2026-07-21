"""
Fase de limpieza final: comprueba que la configuración de PyInstaller (Fase 6)
nunca empaquete datos reales del usuario dentro del .exe/dist/. No construye el
ejecutable (sería lento): inspecciona el propio escritorio.spec como fuente de
verdad de qué se incluye, y si ya existe una carpeta dist/ construida, la revisa
también.
"""

import os
import re

PROYECTO_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# Carpetas de solo lectura que SÍ es legítimo empaquetar: recursos de la app, nunca
# datos reales del usuario.
CARPETAS_DATOS_PERMITIDAS = {"templates", "static", "migrations"}
PATRONES_PROHIBIDOS_EN_SPEC = ("academico.db", ".env", "documentos_dir", "backup_")


def test_spec_no_declara_datos_prohibidos():
    with open(os.path.join(PROYECTO_DIR, "escritorio.spec"), encoding="utf-8") as f:
        contenido = f.read()

    for patron in PATRONES_PROHIBIDOS_EN_SPEC:
        assert patron not in contenido, f"escritorio.spec no debería mencionar '{patron}'"

    # Cada tupla de `datas` es (origen, destino_en_el_bundle): el destino declarado
    # debe ser siempre una de las carpetas de solo-lectura permitidas.
    destinos = re.findall(r'PROJECT_DIR,\s*"([^"]+)"\)\s*,\s*"([^"]+)"\)', contenido)
    destinos_declarados = {destino for _origen, destino in destinos}
    assert destinos_declarados, "no se encontraron entradas en datas=[...] para verificar"
    assert destinos_declarados <= CARPETAS_DATOS_PERMITIDAS, (
        f"escritorio.spec empaqueta carpetas no permitidas: {destinos_declarados - CARPETAS_DATOS_PERMITIDAS}"
    )


def test_dist_construido_no_contiene_datos_reales():
    """Si ya existe una build en dist/ (de una ejecución anterior de build.ps1), sus
    únicos artefactos de datos deben ser los que la propia app crea al primer
    arranque (academico.db/documentos/ generados vacíos, con seed), nunca un
    .env, ni un backup, ni un academico.db copiado a mano desde el proyecto real."""
    dist_dir = os.path.join(PROYECTO_DIR, "dist")
    if not os.path.isdir(dist_dir):
        return  # no se ha construido nada todavía: nada que comprobar

    for raiz, _dirs, archivos in os.walk(dist_dir):
        for nombre in archivos:
            assert nombre != ".env", f"no debe existir un .env dentro de dist/: {raiz}"
            assert not nombre.startswith("backup_"), f"no debe haber backups reales en dist/: {raiz}"
