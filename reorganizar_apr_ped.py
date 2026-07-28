"""
Script puntual de reorganización para APR (asignatura 2) y PRD/PED (asignatura 11):

1) Los proyectos (carpetas "Proyecto ...") dejan de estar desmenuzados en Teoría:
   se borran todos sus documentos/subgrupos ya importados y se sustituyen por UN
   zip global por proyecto (con todo su contenido tal cual, salvo artefactos de
   build), subido a la categoría "otros" en el subgrupo "Proyectos".

2) Los ejercicios resueltos pasan a la categoría "otros":
   - APR: cualquier subgrupo de teoría cuyo nombre contenga "Ejercicios Resueltos".
   - PRD: cualquier subgrupo de teoría de código en C ("C - ...") que no sea de
     un proyecto (son los ejercicios de clase resueltos en C).

Uso:
    python reorganizar_apr_ped.py --target dev
    python reorganizar_apr_ped.py --target dist
"""
import argparse
import os
import shutil
import sys
import tempfile
import unicodedata
import zipfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ONEDRIVE_BASE = r"C:\Users\dmart\OneDrive\Ingenieria Electronica de Telecomunicaciones"

# (asignatura_id, carpeta origen en OneDrive, [nombres de subcarpetas de proyecto])
PROYECTOS = [
    (2, os.path.join(ONEDRIVE_BASE, r"1.º\1.º Cuatrimestre\APR"), ["Proyecto 2023", "Proyecto 2024"]),
    (11, os.path.join(ONEDRIVE_BASE, r"1.º\2.º Cuatrimestre\Programación y Estructuras de Datos"), ["Proyecto 2024"]),
]

DIR_BLACKLIST = {
    "db", "incremental_db", "__pycache__", "dist", ".dist", "build", "nbproject",
    "output_files", ".git", "node_modules", ".metadata", "simulation", "__macosx",
}
EXT_BLACKLIST = {
    "pyc", "o", "obj", "class", "exe", "dll", "so", "a", "lib", "pdb",
    "ilk", "sud", "suo", "bak", "hif", "hdb", "cdb", "cnf", "kpt", "rdb",
    "logdb", "ddb", "rcfdb", "ecobp", "sci", "qmsg", "summary", "cbx",
    "bpm", "mk", "vwf", "qws", "sof", "pof", "jdi", "done", "qdf",
}
NAME_BLACKLIST = {"makefile"}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normaliza(s):
    return strip_accents(s).lower()


def excluido(nombre):
    base, ext = os.path.splitext(nombre)
    ext = ext.lstrip(".").lower()
    return base.lower() in NAME_BLACKLIST or ext in EXT_BLACKLIST


def zipear_proyecto(carpeta_proyecto, ruta_zip_destino):
    with zipfile.ZipFile(ruta_zip_destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(carpeta_proyecto):
            dirnames[:] = [d for d in dirnames if d.lower() not in DIR_BLACKLIST]
            for nombre in filenames:
                if excluido(nombre):
                    continue
                ruta_abs = os.path.join(dirpath, nombre)
                arcname = os.path.relpath(ruta_abs, carpeta_proyecto)
                zf.write(ruta_abs, arcname)


def ejecutar(database_uri=None, documentos_dir=None):
    from app import create_app
    from models import db, Asignatura, GrupoDocumento, Documento
    from utils import carpeta_categoria, carpeta_grupo, ruta_absoluta, nombre_archivo_disponible
    from routes.documentos import _indexar_texto_pdf

    app = create_app(auto_seed=False, database_uri=database_uri, documentos_dir=documentos_dir)
    with app.app_context():

        def get_or_create_grupo(asignatura_id, categoria, nombre):
            grupo = GrupoDocumento.query.filter_by(
                asignatura_id=asignatura_id, categoria=categoria, nombre=nombre
            ).first()
            if not grupo:
                max_orden = db.session.query(db.func.max(GrupoDocumento.orden)).filter_by(
                    asignatura_id=asignatura_id, categoria=categoria
                ).scalar() or 0
                grupo = GrupoDocumento(
                    asignatura_id=asignatura_id, categoria=categoria, nombre=nombre, orden=max_orden + 1,
                )
                db.session.add(grupo)
                db.session.flush()
            return grupo

        def borrar_grupo_y_documentos(grupo):
            for doc in list(grupo.documentos):
                ruta = ruta_absoluta(doc.ruta_local)
                if os.path.exists(ruta):
                    os.remove(ruta)
                db.session.delete(doc)
            db.session.flush()
            carpeta = carpeta_grupo(grupo.asignatura, grupo)
            if os.path.isdir(carpeta):
                shutil.rmtree(carpeta, ignore_errors=True)
            db.session.delete(grupo)

        # --- 1) Consolidar proyectos ---
        tmp_dir = tempfile.mkdtemp(prefix="reorg_proyectos_")
        try:
            for asignatura_id, carpeta_asignatura_origen, nombres_proyecto in PROYECTOS:
                asignatura = Asignatura.query.get(asignatura_id)
                if asignatura is None:
                    print(f"AVISO: asignatura {asignatura_id} no existe")
                    continue

                grupo_proyectos = get_or_create_grupo(asignatura_id, "otros", "Proyectos")

                for nombre_proyecto in nombres_proyecto:
                    print(f"--- asignatura {asignatura_id}: proyecto '{nombre_proyecto}' ---")
                    # Borra todos los subgrupos (en cualquier categoría) que pertenezcan
                    # a este proyecto (nombre = nombre_proyecto o empieza por
                    # "nombre_proyecto - ").
                    grupos_proyecto = GrupoDocumento.query.filter_by(asignatura_id=asignatura_id).filter(
                        db.or_(
                            GrupoDocumento.nombre == nombre_proyecto,
                            GrupoDocumento.nombre.like(f"{nombre_proyecto} - %"),
                        )
                    ).all()
                    print(f"    borrando {len(grupos_proyecto)} subgrupos ya importados")
                    for g in grupos_proyecto:
                        borrar_grupo_y_documentos(g)
                    db.session.flush()

                    carpeta_origen = os.path.join(carpeta_asignatura_origen, nombre_proyecto)
                    if not os.path.isdir(carpeta_origen):
                        print(f"    AVISO: no existe {carpeta_origen}")
                        continue

                    ruta_zip_tmp = os.path.join(tmp_dir, f"{asignatura_id}_{nombre_proyecto}.zip")
                    zipear_proyecto(carpeta_origen, ruta_zip_tmp)

                    carpeta_destino = carpeta_grupo(asignatura, grupo_proyectos)
                    os.makedirs(carpeta_destino, exist_ok=True)
                    nombre_final = nombre_archivo_disponible(carpeta_destino, f"{nombre_proyecto}.zip")
                    destino = os.path.join(carpeta_destino, nombre_final)
                    shutil.copy2(ruta_zip_tmp, destino)

                    ruta_relativa = os.path.relpath(destino, app.config["DOCUMENTOS_DIR"]).replace(os.sep, "/")
                    documento = Documento(
                        asignatura_id=asignatura.id,
                        categoria="otros",
                        grupo_documento_id=grupo_proyectos.id,
                        nombre_archivo=nombre_final,
                        nombre_original=f"{nombre_proyecto}.zip",
                        ruta_local=ruta_relativa,
                        tamano_bytes=os.path.getsize(destino),
                        fecha_subida=datetime.utcnow(),
                    )
                    db.session.add(documento)
                    print(f"    subido {nombre_final} ({documento.tamano_bytes} bytes)")

            db.session.commit()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # --- 2) Ejercicios resueltos -> otros ---
        def mover_grupo_a_otros(grupo):
            asignatura = grupo.asignatura
            origen = carpeta_grupo(asignatura, grupo)
            grupo.categoria = "otros"
            db.session.flush()  # para que carpeta_grupo ya calcule la ruta destino con la nueva categoría
            destino = carpeta_grupo(asignatura, grupo)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            if os.path.isdir(origen) and origen != destino:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                shutil.move(origen, destino)
            for doc in grupo.documentos:
                doc.categoria = "otros"

        # APR: subgrupos de teoría con "Ejercicios Resueltos" en el nombre
        grupos_apr = GrupoDocumento.query.filter_by(asignatura_id=2, categoria="teoria").filter(
            GrupoDocumento.nombre.ilike("%Ejercicios Resueltos%")
        ).all()
        print(f"APR: moviendo {len(grupos_apr)} subgrupos de 'Ejercicios Resueltos' a otros")
        for g in grupos_apr:
            mover_grupo_a_otros(g)

        # PRD: subgrupos de teoría de código en C que no sean de un proyecto
        grupos_ped = GrupoDocumento.query.filter_by(asignatura_id=11, categoria="teoria").filter(
            GrupoDocumento.nombre.like("C -%")
        ).all()
        print(f"PRD: moviendo {len(grupos_ped)} subgrupos de ejercicios en C a otros")
        for g in grupos_ped:
            mover_grupo_a_otros(g)

        db.session.commit()
        print("Reorganización completada.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["dev", "dist"], default="dev")
    args = parser.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    if args.target == "dist":
        database_uri = f"sqlite:///{os.path.join(base, 'dist', 'academico.db')}"
        documentos_dir = os.path.join(base, "dist", "documentos")
    else:
        database_uri = None
        documentos_dir = None
    ejecutar(database_uri=database_uri, documentos_dir=documentos_dir)


if __name__ == "__main__":
    main()
