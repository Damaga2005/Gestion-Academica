# -*- coding: utf-8 -*-
"""
Script puntual: añade un recurso "Studocu" a las asignaturas cuya página de
curso en Studocu se pudo confirmar (5 por código oficial UPC en el título de
la página; el resto verificados a mano por el usuario navegando el índice de
cursos de la universidad en Studocu, que no se pudo automatizar de forma
fiable — ver conversación).

Uso:
    python cargar_studocu.py --target dev
    python cargar_studocu.py --target dist
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# asignatura_id -> URL completa de la página de curso en Studocu
CONFIRMADOS = {
    1: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/algebra-lineal/1665471",
    3: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/calculo/3108508",
    4: "https://www.studocu.com/ca-es/course/universitat-politecnica-de-catalunya/components-i-circuits-electronics/4303914",  # CCE - 230900
    5: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/fisica/4303911",
    7: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/circuit-analysis/2129453",
    8: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/calcul-vectorial/1665614",
    9: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/matematiques-de-la-telecomunicacio/1668883",
    10: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/electromagnetismo/3108591",
    12: "https://www.studocu.com/ca-es/course/universitat-politecnica-de-catalunya/dispositius-electronics/4337755",  # DE - 230910
    13: "https://www.studocu.com/ca-es/course/universitat-politecnica-de-catalunya/electromagnetisme-i-fotonica-aplicada/5479023",  # EAFO - 230912
    14: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/ppe-probabilitat-i-procesos-estocastics/5133866",
    15: "https://www.studocu.com/ca-es/course/universitat-politecnica-de-catalunya/senyals-i-sistemes/1666674",  # SST - 230913
    16: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/disseny-digital/1668545",
    25: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/circuits-analogics/5586657",
    26: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/ep-empresa-y-proyectos/5285450",
    27: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/icaf-introduccion-a-los-circuitos-de-alta-frecuencia/5285452",
    28: "https://www.studocu.com/ca-es/course/universitat-politecnica-de-catalunya/sistemes-encastats/4530428",  # EMB - 230916
    29: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/tractament-del-senyal/4839756",
    30: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/ciencia-e-ingenieria-de-materiales/6918960",
    31: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/sistemes-de-control/5158889",
    32: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/sistemes-de-mesura/4824492",
    33: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/sistemes-digitals-configurables/5072376",
    34: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/circuits-dalta-frequencia/5072375",
    38: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/iot/3108664",
    39: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/processat-denergia-electrica/6976375",
    40: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/sistemes-en-temps-real/6176247",
    41: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/tem-tecnicas-para-el-emprendimiento/6003876",
    42: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/tecnologia-electronica/5289135",
    44: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/disseny-microelectronic/6599387",
    47: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/telecomunicacio-espacial/6953678",
    52: "https://www.studocu.com/es/course/universitat-politecnica-de-catalunya/matlab-y-sus-aplicaciones-en-la-ingenieria/3108677",
}


def ejecutar(database_uri=None, documentos_dir=None):
    from app import create_app
    from models import db, Asignatura, RecursoExterno
    from sqlalchemy import func

    app = create_app(auto_seed=False, database_uri=database_uri, documentos_dir=documentos_dir)
    with app.app_context():
        for asignatura_id, url in CONFIRMADOS.items():
            asignatura = Asignatura.query.get(asignatura_id)
            if asignatura is None:
                print(f"AVISO: asignatura {asignatura_id} no existe, se omite")
                continue

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
