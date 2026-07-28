# -*- coding: utf-8 -*-
"""
Script puntual: añade un recurso "Studocu" a las asignaturas cuya página de
curso en Studocu se pudo confirmar de forma fiable (el código oficial UPC
aparece literalmente en el título de la página de Studocu, p. ej.
"Components i Circuits Electrònics - 230900 - UPC - Studocu").

La búsqueda por código para el resto de asignaturas fue demasiado ruidosa
(códigos numéricos de 6 cifras coinciden con IDs de documentos de cualquier
universidad del mundo) como para confirmar el resto sin arriesgarse a
enlazar la asignatura equivocada, así que solo se cargan las confirmadas.

Uso:
    python cargar_studocu.py --target dev
    python cargar_studocu.py --target dist
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "https://www.studocu.com/ca-es/course/universitat-politecnica-de-catalunya/"

# asignatura_id -> slug/id de Studocu (confirmados por código oficial UPC en el título)
CONFIRMADOS = {
    4: "components-i-circuits-electronics/4303914",    # CCE - 230900
    12: "dispositius-electronics/4337755",              # DE - 230910
    13: "electromagnetisme-i-fotonica-aplicada/5479023",  # EAFO - 230912
    15: "senyals-i-sistemes/1666674",                    # SST - 230913 (código legado 230088 en la página)
    28: "sistemes-encastats/4530428",                    # EMB - 230916
}


def ejecutar(database_uri=None, documentos_dir=None):
    from app import create_app
    from models import db, Asignatura, RecursoExterno
    from sqlalchemy import func

    app = create_app(auto_seed=False, database_uri=database_uri, documentos_dir=documentos_dir)
    with app.app_context():
        for asignatura_id, ruta in CONFIRMADOS.items():
            asignatura = Asignatura.query.get(asignatura_id)
            if asignatura is None:
                print(f"AVISO: asignatura {asignatura_id} no existe, se omite")
                continue

            url = f"{BASE_URL}{ruta}"
            existente = RecursoExterno.query.filter_by(asignatura_id=asignatura_id, nombre="Studocu").first()
            if existente:
                existente.url = url
                print(f"asignatura {asignatura_id} ({asignatura.nombre}): recurso Studocu actualizado")
                continue

            max_orden = db.session.query(func.max(RecursoExterno.orden)).filter_by(
                asignatura_id=asignatura_id
            ).scalar() or 0
            db.session.add(RecursoExterno(
                asignatura_id=asignatura_id, nombre="Studocu", url=url, orden=max_orden + 1,
            ))
            print(f"asignatura {asignatura_id} ({asignatura.nombre}): recurso Studocu añadido")

        db.session.commit()
        print("Completado.")


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
