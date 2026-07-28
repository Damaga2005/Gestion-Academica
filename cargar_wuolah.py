# -*- coding: utf-8 -*-
"""
Script puntual: añade un recurso "Wuolah" (enlace a la comunidad de apuntes) a
cada asignatura que tiene una carpeta equivalente en
https://wuolah.com/upc-escuela-tecnica-superior-ingenieria-telecomuni/grado-ingenieria-electronica-telecomunicacion

Solo se añaden las asignaturas con una correspondencia de nombre razonablemente
clara; las que no tienen equivalente en Wuolah (o cuyo nombre en Wuolah parece
un curso distinto) se dejan fuera a propósito.

Uso:
    python cargar_wuolah.py --target dev
    python cargar_wuolah.py --target dist
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "https://wuolah.com/apuntes/"
COMMUNITY = "?communityId=41753"

# asignatura_id -> (slug de Wuolah, f_course tal cual aparece en wuolah.com)
SLUGS = {
    1: ("algebra-lineal", 1),
    2: ("algoritmia-y-programacion", 1),
    3: ("calculo", 1),
    4: ("componentes-y-circuitos-electronicos", 1),
    5: ("fisica", 1),
    6: ("introduccion-a-las-matematicas", 1),
    7: ("analisis-de-circuitos", 1),
    8: ("calculo-vectorial", 1),
    9: ("ecuaciones-diferenciales-y-transformadas", 1),
    10: ("electromagnetismo", 1),
    11: ("programacion-y-estructura-de-datos-2", 1),
    12: ("dispositivos-electronicos", 2),
    13: ("electromagnetismo-aplicado-y-fotonica", 2),
    14: ("probabilidad-y-procesos-estocasticos", 2),
    15: ("senales-y-sistemas", 2),
    16: ("diseno-digital", 2),
    17: ("administracion-de-sistemas-linux", 2),
    18: ("algebra-lineal-codigos-lineales-y-esquemas-de-comparticion-de-secretos", 2),
    19: ("crear-tu-futuro-un-simple-trabajo-o-tu-autentica-pasion", 2),
    21: ("la-ingenieria-financiera-en-la-planificacion-economica-de-inversiones", 2),
    22: ("liderazgo-y-tecnicas-de-desarrollo-profesional-en-la-ingenieria", 2),
    23: ("proyecto-de-cooperacion-con-tecnologias-wifi", 2),
    24: ("simulacion-y-analisis-de-circuitos-mediante-pspice", 2),
    25: ("circuitos-analogicos", 2),
    26: ("empresa-y-proyectos", 2),
    27: ("introduccion-a-los-circuitos-de-alta-frecuencia", 2),
    28: ("sistemas-embebidos", 2),
    29: ("tratamiento-de-senales", 2),
    30: ("ciencia-e-ingenieria-de-materiales", 3),
    31: ("sistemas-de-control", 3),
    32: ("sistemas-de-medida", 3),
    33: ("sistemas-digitales-configurables", 3),
    34: ("circuitos-de-alta-frecuencia", 3),
    35: ("aprendizaje-automatico", 2),
    36: ("introduccion-al-aprendizaje-profundo", 3),
    38: ("internet-de-las-cosas", 3),
    39: ("procesado-de-energia-electrica", 3),
    40: ("sistemas-en-tiempo-real", 3),
    41: ("tecnicas-para-el-emprendimiento", 3),
    42: ("tecnologia-electronica", 3),
    43: ("electronica-del-automovil", 4),  # nombre distinto en Wuolah, misma temática
    44: ("diseno-microelectronico", 4),
    45: ("integracion-de-sistemas", 4),
    46: ("sistemas-hardware-de-procesado-de-informacion", 4),
    48: ("sensores-actuadores-y-microcontroladores-en-robots-moviles", 4),
    49: ("aprendizaje-por-refuerzo-y-aprendizaje-profundo", 4),
    50: ("dispositivos-fotovoltaicos", 4),
    51: ("electronica-inteligente", 4),
    52: ("matlab-y-sus-aplicaciones-en-ingenieria", 4),
    54: ("trabajo-de-fin-de-grado", 4),
    # Sin correspondencia clara en Wuolah, omitidas a propósito:
    # 20 (Ética para la Ingeniería), 37 (Resolución de Problemas con IA),
    # 47 (Telecomunicación Espacial), 53 (Seguridad y Privacidad de la Información)
}


def ejecutar(database_uri=None, documentos_dir=None):
    from app import create_app
    from models import db, Asignatura, RecursoExterno
    from sqlalchemy import func

    app = create_app(auto_seed=False, database_uri=database_uri, documentos_dir=documentos_dir)
    with app.app_context():
        creados = 0
        for asignatura_id, (slug, f_course) in SLUGS.items():
            asignatura = Asignatura.query.get(asignatura_id)
            if asignatura is None:
                print(f"AVISO: asignatura {asignatura_id} no existe, se omite")
                continue

            url = f"{BASE_URL}{slug}{COMMUNITY}&f_course={f_course}"
            existente = RecursoExterno.query.filter_by(asignatura_id=asignatura_id, nombre="Wuolah").first()
            if existente:
                existente.url = url
                print(f"asignatura {asignatura_id} ({asignatura.nombre}): recurso Wuolah actualizado")
                continue

            max_orden = db.session.query(func.max(RecursoExterno.orden)).filter_by(
                asignatura_id=asignatura_id
            ).scalar() or 0
            db.session.add(RecursoExterno(
                asignatura_id=asignatura_id, nombre="Wuolah", url=url, orden=max_orden + 1,
            ))
            creados += 1
            print(f"asignatura {asignatura_id} ({asignatura.nombre}): recurso Wuolah añadido")

        db.session.commit()
        print(f"Completado: {creados} recursos Wuolah nuevos.")


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
