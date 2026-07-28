"""
Script puntual para importar los apuntes/documentos de OneDrive (subcarpetas de
1.º y 2.º) a la app de gestión académica, organizados por asignatura/categoría/subgrupo.

Uso:
    python import_apuntes.py --dry-run   # solo informa, no toca nada
    python import_apuntes.py --apply     # ejecuta la importación real
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import zipfile
from collections import defaultdict
from datetime import datetime

from werkzeug.utils import secure_filename

ONEDRIVE_BASE = r"C:\Users\dmart\OneDrive\Ingenieria Electronica de Telecomunicaciones"

# --- Mapeo carpeta OneDrive -> asignatura_id ------------------------------------
FOLDER_TO_ASIGNATURA = {
    r"1.º\1.º Cuatrimestre\Algebra Lineal": 1,
    r"1.º\1.º Cuatrimestre\APR": 2,
    r"1.º\1.º Cuatrimestre\Calculo": 3,
    r"1.º\1.º Cuatrimestre\CCE": 4,
    r"1.º\1.º Cuatrimestre\Fisica": 5,
    r"1.º\2.º Cuatrimestre\Analisis de Circuitos": 7,
    r"1.º\2.º Cuatrimestre\Calculo Vectorial": 8,
    r"1.º\2.º Cuatrimestre\Ecucaciones Diferenciales y Transformadas": 9,
    r"1.º\2.º Cuatrimestre\Electromagnetismo": 10,
    r"1.º\2.º Cuatrimestre\Programación y Estructuras de Datos": 11,
    r"2.º\1.º Cuatrimestre\DE (Grupo 12)": 12,
    r"2.º\1.º Cuatrimestre\EAFO (Grupo 12)": 13,
    r"2.º\1.º Cuatrimestre\PPE": 14,
    r"2.º\1.º Cuatrimestre\SST (Grupo 12)": 15,
    r"2.º\1.º Cuatrimestre\DD (Grupo 14)": 16,
    r"2.º\2.º Cuatrimestre\ICAF": 27,
    r"2.º\2.º Cuatrimestre\CIAF": 27,
}

ALLOWED_EXTS = {
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "rtf",
    "odt", "ods", "odp", "csv", "md", "zip",
    "jpg", "jpeg", "png", "gif", "webp", "bmp",
}
ZIP_CODE_EXTS = {"c", "h", "m", "mlx", "vhd", "py"}  # código: se agrupan en un zip por subgrupo

DIR_BLACKLIST = {
    "db", "incremental_db", "__pycache__", "dist", "build", "nbproject",
    "output_files", ".git", "node_modules", ".metadata", "simulation",
}
EXT_BLACKLIST = {
    "pyc", "o", "obj", "class", "exe", "dll", "so", "a", "lib", "pdb",
    "ilk", "sud", "suo", "bak", "hif", "hdb", "cdb", "cnf", "kpt", "rdb",
    "logdb", "ddb", "rcfdb", "ecobp", "sci", "qmsg", "summary", "cbx",
    "bpm", "mk", "vwf", "qws", "sof", "pof", "jdi", "done", "qdf",
}
NAME_BLACKLIST = {"makefile"}

CATEGORIA_KEYWORDS = {
    "laboratorios": ("laborator", "practica", "pràctica", "práctica"),
    "examenes": ("examen", "exámenes", "exàmens", "parcial", "final", "control"),
    "teoria": ("teoria", "teoría",),
}
# Para quitar del nombre del subgrupo SOLO carpetas cuyo nombre es prácticamente
# el propio rótulo de la categoría (coincidencia exacta, no solo "contiene"):
# así "Laboratorio 26" se conserva como subgrupo con su número, y solo se quita
# una carpeta llamada literalmente "Laboratorio"/"Teoria"/"Examenes".
ETIQUETAS_EXACTAS_CATEGORIA = {
    "laboratorios": {"laboratorio", "laboratorios", "practica", "practicas", "pràctica", "practiques"},
    "examenes": {"examen", "examenes", "exàmens", "examens"},
    "teoria": {"teoria", "teoría"},
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normaliza(s):
    return strip_accents(s).lower()


def clasificar_categoria(partes_ruta, nombre_archivo_sin_ext):
    """Clasifica SOLO a partir de las carpetas (nunca del nombre de archivo, para no
    reclasificar p. ej. 'Teoria/Primer Control.pdf' como examen por la palabra
    'Control' en el nombre). El nombre de archivo solo decide cuando el archivo
    está directamente en la raíz de la asignatura (sin ninguna carpeta intermedia)."""
    tokens = list(partes_ruta) if partes_ruta else [nombre_archivo_sin_ext]
    for i, token in enumerate(tokens):
        tok_norm = normaliza(token)
        for categoria in ("laboratorios", "examenes", "teoria"):
            keywords = CATEGORIA_KEYWORDS[categoria]
            if any(normaliza(kw) in tok_norm for kw in keywords):
                return categoria, (i if partes_ruta else None)
    return "teoria", None


def excluido(partes_ruta, nombre_archivo):
    for p in partes_ruta:
        if p.lower() in DIR_BLACKLIST:
            return True
    base, ext = os.path.splitext(nombre_archivo)
    ext = ext.lstrip(".").lower()
    if base.lower() in NAME_BLACKLIST:
        return True
    if ext in EXT_BLACKLIST:
        return True
    return False


def construir_items():
    """
    Recorre todas las carpetas mapeadas y devuelve dos listas:
      - directos: [(asignatura_id, categoria, subgrupo_o_None, ruta_abs_origen, nombre_archivo)]
      - zips: dict {(asignatura_id, categoria, subgrupo_o_None): [(ruta_abs_origen, arcname)]}
    y un contador de excluidos por extensión para el informe.
    """
    directos = []
    zips = defaultdict(list)
    excluidos_ext = defaultdict(int)
    omitidos_codigo_ext = defaultdict(int)

    for rel_folder, asignatura_id in FOLDER_TO_ASIGNATURA.items():
        raiz = os.path.join(ONEDRIVE_BASE, rel_folder)
        if not os.path.isdir(raiz):
            print(f"AVISO: no existe la carpeta {raiz}", file=sys.stderr)
            continue

        for dirpath, dirnames, filenames in os.walk(raiz):
            dirnames[:] = [d for d in dirnames if d.lower() not in DIR_BLACKLIST]
            rel_dir = os.path.relpath(dirpath, raiz)
            partes = [] if rel_dir == "." else rel_dir.split(os.sep)

            for nombre in filenames:
                if excluido(partes, nombre):
                    base, ext = os.path.splitext(nombre)
                    excluidos_ext[ext.lstrip(".").lower() or "(sin ext)"] += 1
                    continue

                base, ext = os.path.splitext(nombre)
                ext = ext.lstrip(".").lower()
                categoria, _idx_disparo = clasificar_categoria(partes, base)

                # subgrupo = partes de carpeta, quitando cualquiera que sea
                # sinónimo de la categoría ya asignada (evita "Teoria - Tema 1"
                # dentro de la categoría teoria, "Examenes - Parciales" dentro
                # de examenes, etc.)
                etiquetas_exactas = ETIQUETAS_EXACTAS_CATEGORIA[categoria]
                partes_subgrupo = [
                    p for p in partes if normaliza(p) not in etiquetas_exactas
                ]
                subgrupo = " - ".join(partes_subgrupo) if partes_subgrupo else None

                ruta_abs = os.path.join(dirpath, nombre)

                if ext in ALLOWED_EXTS:
                    directos.append((asignatura_id, categoria, subgrupo, ruta_abs, nombre))
                elif ext in ZIP_CODE_EXTS:
                    arcname = os.path.join(*partes, nombre) if partes else nombre
                    zips[(asignatura_id, categoria, subgrupo)].append((ruta_abs, arcname))
                else:
                    omitidos_codigo_ext[ext or "(sin ext)"] += 1

    return directos, zips, excluidos_ext, omitidos_codigo_ext


def imprimir_informe(directos, zips, excluidos_ext, omitidos_codigo_ext):
    print("=" * 70)
    print("INFORME DE IMPORTACIÓN (dry-run)")
    print("=" * 70)

    por_asig = defaultdict(lambda: defaultdict(int))
    for asignatura_id, categoria, _sub, _ruta, _nombre in directos:
        por_asig[asignatura_id][categoria] += 1

    print("\n-- Archivos a subir directamente, por asignatura --")
    for asignatura_id in sorted(por_asig):
        total = sum(por_asig[asignatura_id].values())
        detalle = ", ".join(f"{c}={n}" for c, n in por_asig[asignatura_id].items())
        print(f"  asignatura {asignatura_id}: {total} archivos ({detalle})")
    print(f"  TOTAL directos: {len(directos)}")

    print("\n-- Zips de código (.c/.h/.m) a generar --")
    total_zip_files = 0
    for (asignatura_id, categoria, subgrupo), archivos in sorted(zips.items()):
        total_zip_files += len(archivos)
        print(f"  asignatura {asignatura_id} / {categoria} / {subgrupo or '(sin subgrupo)'}: "
              f"{len(archivos)} archivos -> 1 zip")
    print(f"  TOTAL zips: {len(zips)}  (empaquetando {total_zip_files} archivos de código)")

    print("\n-- Excluidos (artefactos de build, no se tocan) --")
    for ext, n in sorted(excluidos_ext.items(), key=lambda x: -x[1]):
        print(f"  .{ext}: {n}")
    print(f"  TOTAL excluidos: {sum(excluidos_ext.values())}")

    print("\n-- Omitidos (código fuente distinto de .c/.h/.m, no soportado por la app) --")
    for ext, n in sorted(omitidos_codigo_ext.items(), key=lambda x: -x[1]):
        print(f"  .{ext}: {n}")
    print(f"  TOTAL omitidos: {sum(omitidos_codigo_ext.values())}")


def ejecutar_importacion(directos, zips, database_uri=None, documentos_dir=None, solo_zips=False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app import create_app
    from models import db, Asignatura, GrupoDocumento, Documento
    from utils import carpeta_categoria, carpeta_grupo, nombre_archivo_disponible
    from routes.documentos import _indexar_texto_pdf

    app = create_app(auto_seed=False, database_uri=database_uri, documentos_dir=documentos_dir)
    creados = 0
    with app.app_context():
        grupo_cache = {}

        def get_or_create_grupo(asignatura_id, categoria, nombre):
            if nombre is None:
                return None
            key = (asignatura_id, categoria, nombre)
            if key in grupo_cache:
                return grupo_cache[key]
            grupo = GrupoDocumento.query.filter_by(
                asignatura_id=asignatura_id, categoria=categoria, nombre=nombre
            ).first()
            if not grupo:
                max_orden = db.session.query(db.func.max(GrupoDocumento.orden)).filter_by(
                    asignatura_id=asignatura_id, categoria=categoria
                ).scalar() or 0
                grupo = GrupoDocumento(
                    asignatura_id=asignatura_id, categoria=categoria,
                    nombre=nombre[:120], orden=max_orden + 1,
                )
                db.session.add(grupo)
                db.session.flush()
            grupo_cache[key] = grupo
            return grupo

        def subir(asignatura, categoria, grupo, ruta_origen, nombre_deseado):
            nonlocal creados
            carpeta = carpeta_grupo(asignatura, grupo) if grupo else carpeta_categoria(asignatura, categoria)
            os.makedirs(carpeta, exist_ok=True)
            nombre_seguro = secure_filename(os.path.basename(nombre_deseado))
            nombre_final = nombre_archivo_disponible(carpeta, nombre_seguro)
            destino = os.path.join(carpeta, nombre_final)
            shutil.copy2(ruta_origen, destino)

            ruta_relativa = os.path.relpath(destino, app.config["DOCUMENTOS_DIR"]).replace(os.sep, "/")
            documento = Documento(
                asignatura_id=asignatura.id,
                categoria=categoria,
                grupo_documento_id=grupo.id if grupo else None,
                nombre_archivo=nombre_final,
                nombre_original=os.path.basename(nombre_deseado)[:255],
                ruta_local=ruta_relativa,
                tamano_bytes=os.path.getsize(destino),
                fecha_subida=datetime.utcnow(),
            )
            db.session.add(documento)
            db.session.flush()
            if documento.es_pdf():
                _indexar_texto_pdf(documento)
            creados += 1

        asignatura_cache = {}

        def get_asignatura(asignatura_id):
            if asignatura_id not in asignatura_cache:
                asignatura_cache[asignatura_id] = Asignatura.query.get(asignatura_id)
            return asignatura_cache[asignatura_id]

        # 1) Archivos directos
        if not solo_zips:
            for asignatura_id, categoria, subgrupo, ruta_abs, nombre in directos:
                asignatura = get_asignatura(asignatura_id)
                if asignatura is None:
                    print(f"AVISO: asignatura {asignatura_id} no existe, se omite {ruta_abs}", file=sys.stderr)
                    continue
                grupo = get_or_create_grupo(asignatura_id, categoria, subgrupo)
                subir(asignatura, categoria, grupo, ruta_abs, nombre)

        db.session.commit()

        # 2) Zips de código
        tmp_dir = tempfile.mkdtemp(prefix="import_apuntes_zip_")
        try:
            for (asignatura_id, categoria, subgrupo), archivos in zips.items():
                asignatura = get_asignatura(asignatura_id)
                if asignatura is None:
                    continue
                nombre_zip = f"Codigo - {subgrupo}.zip" if subgrupo else "Codigo.zip"
                nombre_zip = re.sub(r"[\\/:*?\"<>|]", "_", nombre_zip)
                ruta_zip_tmp = os.path.join(tmp_dir, f"{asignatura_id}_{categoria}_{abs(hash((subgrupo,categoria)))}.zip")
                with zipfile.ZipFile(ruta_zip_tmp, "w", zipfile.ZIP_DEFLATED) as zf:
                    for ruta_abs, arcname in archivos:
                        zf.write(ruta_abs, arcname)

                grupo = get_or_create_grupo(asignatura_id, categoria, subgrupo)
                subir(asignatura, categoria, grupo, ruta_zip_tmp, nombre_zip)

            db.session.commit()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"Importación completada: {creados} documentos creados.")


def main():
    parser = argparse.ArgumentParser()
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--dry-run", action="store_true")
    grupo.add_argument("--apply", action="store_true")
    parser.add_argument("--target", choices=["dev", "dist"], default="dev",
                         help="dev = academico.db del proyecto; dist = dist/academico.db del .exe empaquetado")
    parser.add_argument("--only-zips", action="store_true",
                         help="no vuelve a subir los archivos directos, solo (re)genera los zips de código")
    args = parser.parse_args()

    directos, zips, excluidos_ext, omitidos_codigo_ext = construir_items()

    if args.dry_run:
        imprimir_informe(directos, zips, excluidos_ext, omitidos_codigo_ext)
    else:
        imprimir_informe(directos, zips, excluidos_ext, omitidos_codigo_ext)
        print(f"\nEjecutando importación real (target={args.target})...\n")
        base = os.path.dirname(os.path.abspath(__file__))
        if args.target == "dist":
            database_uri = f"sqlite:///{os.path.join(base, 'dist', 'academico.db')}"
            documentos_dir = os.path.join(base, "dist", "documentos")
        else:
            database_uri = None
            documentos_dir = None
        ejecutar_importacion(directos, zips, database_uri=database_uri, documentos_dir=documentos_dir,
                             solo_zips=args.only_zips)


if __name__ == "__main__":
    main()
