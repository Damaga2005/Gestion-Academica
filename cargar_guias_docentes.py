# -*- coding: utf-8 -*-
"""
Script puntual: carga siglas oficiales, profesorado y esquemas de evaluación
extraídos de las guías docentes UPC (Downloads/GUIAS ALUMNOS/GD-*.pdf) para las
15 asignaturas ya documentadas en la app.

Es idempotente por asignatura: si ya tiene profesores o esquemas, no duplica
(borra y vuelve a crear), para poder relanzarlo sin miedo.

Uso:
    python cargar_guias_docentes.py --target dev
    python cargar_guias_docentes.py --target dist
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATOS = {
    1: {  # Álgebra Lineal
        "siglas": "ALN",
        "profesores": [
            {"nombre": "Francisco Javier Muñoz Lopez", "rol": "Responsable (grupo 10)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Controles", "tipo": "parcial", "porcentaje": 40},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
        ],
    },
    2: {  # Algoritmia y Programación
        "siglas": "APR",
        "profesores": [
            {"nombre": "Eva Rodriguez Luna", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Juan Carlos Cruellas Ibarz", "rol": "Grupo 11"},
        ],
        "esquemas": [
            {"nombre": "Con examen parcial", "componentes": [
                {"nombre": "Examen parcial", "tipo": "parcial", "porcentaje": 20},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 40},
                {"nombre": "Examen laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Proyecto", "tipo": "otro", "porcentaje": 20},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
                {"nombre": "Examen laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Proyecto", "tipo": "otro", "porcentaje": 20},
            ]},
        ],
    },
    3: {  # Cálculo
        "siglas": "C",
        "profesores": [
            {"nombre": "Josep Maria Aroca Farrerons", "rol": "Responsable (grupo 10)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Evaluación continua", "tipo": "parcial", "porcentaje": 40},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
        ],
    },
    4: {  # Componentes y Circuitos Electrónicos
        "siglas": "CCE",
        "profesores": [
            {"nombre": "Alberto Orpella Garcia", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Pablo Rafael Ortega Villasclaras", "rol": "Grupos 11, 12, 13"},
        ],
        "esquemas": [
            {"nombre": "Con examen parcial", "componentes": [
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 10},
                {"nombre": "Problemas", "tipo": "otro", "porcentaje": 10},
                {"nombre": "Examen parcial", "tipo": "parcial", "porcentaje": 30},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 50},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 10},
                {"nombre": "Problemas", "tipo": "otro", "porcentaje": 10},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 80},
            ]},
        ],
    },
    5: {  # Física
        "siglas": "F",
        "profesores": [
            {"nombre": "Vicente Gomis Arbones", "rol": "Responsable (grupo 10)"},
        ],
        "esquemas": [
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 100},
            ]},
            {"nombre": "Con evaluación continua", "componentes": [
                {"nombre": "Evaluación continua", "tipo": "parcial", "porcentaje": 40},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
        ],
    },
    7: {  # Análisis de Circuitos
        "siglas": "AC",
        "profesores": [
            {"nombre": "Manuel Maria Dominguez Pumar", "rol": "Responsable (grupo 10)"},
            {"nombre": "Alexandra Bermejo Broto", "rol": "Grupo 10"},
        ],
        "esquemas": [
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 100},
            ]},
            {"nombre": "Con examen parcial", "componentes": [
                {"nombre": "Examen parcial", "tipo": "parcial", "porcentaje": 30},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 70},
            ]},
        ],
    },
    8: {  # Cálculo Vectorial
        "siglas": "CVEC",
        "profesores": [
            {"nombre": "Carles Padro Laimon", "rol": "Responsable (grupo 10)"},
            {"nombre": "Maria Bras Amoros", "rol": "Grupo 10"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Evaluación continua", "tipo": "parcial", "porcentaje": 40},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
        ],
    },
    9: {  # Ecuaciones Diferenciales y Transformadas
        "siglas": "EDT",
        "profesores": [
            {"nombre": "Josep Maria Aroca Farrerons", "rol": "Responsable (grupo 10)"},
        ],
        "esquemas": [
            {"nombre": "Con parciales", "componentes": [
                {"nombre": "Exámenes parciales", "tipo": "parcial", "porcentaje": 40},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 100},
            ]},
        ],
    },
    10: {  # Electromagnetismo
        "siglas": "EMG",
        "profesores": [
            {"nombre": "Oriol Batiste Boleda", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Jose Eduardo Garcia Garcia", "rol": "Grupos 11, 12, 13"},
            {"nombre": "Jose Miguel Juan Zornoza", "rol": "Grupos 11, 12, 13"},
        ],
        "esquemas": [
            {"nombre": "Con evaluación continuada", "componentes": [
                {"nombre": "Trabajo experimental", "tipo": "laboratorio", "porcentaje": 15},
                {"nombre": "Evaluación continuada", "tipo": "parcial", "porcentaje": 25},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Trabajo experimental", "tipo": "laboratorio", "porcentaje": 15},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 85},
            ]},
        ],
    },
    11: {  # Programación y Estructuras de Datos
        "siglas": "PRD",
        "profesores": [
            {"nombre": "Jordi Perello Muntan", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Silvia Llorente Viejo", "rol": "Grupo 13"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Proyecto de laboratorio", "tipo": "otro", "porcentaje": 10.5},
                {"nombre": "Examen parcial de laboratorio", "tipo": "laboratorio", "porcentaje": 10.5},
                {"nombre": "Examen final de laboratorio", "tipo": "laboratorio", "porcentaje": 14},
                {"nombre": "Examen parcial de teoría", "tipo": "parcial", "porcentaje": 15},
                {"nombre": "Examen final de la asignatura", "tipo": "examen_final", "porcentaje": 50},
            ]},
        ],
    },
    12: {  # Dispositivos Electrónicos
        "siglas": "DE",
        "profesores": [
            {"nombre": "Isidro Martin Garcia", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Alexandra Bermejo Broto", "rol": "Grupos 11, 12, 13"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 10},
                {"nombre": "Parciales y problemas", "tipo": "parcial", "porcentaje": 45},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 45},
            ]},
        ],
    },
    13: {  # Electromagnetismo Aplicado y Fotónica
        "siglas": "EAFO",
        "profesores": [
            {"nombre": "María Concepción Santos Blanco", "rol": "Responsable (grupos 11, 12, 13)"},
        ],
        "esquemas": [
            {"nombre": "Con evaluación continua", "componentes": [
                {"nombre": "Prácticas de laboratorio", "tipo": "laboratorio", "porcentaje": 10},
                {"nombre": "Evaluación continua", "tipo": "parcial", "porcentaje": 30},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Prácticas de laboratorio", "tipo": "laboratorio", "porcentaje": 10},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 90},
            ]},
        ],
    },
    14: {  # Probabilidad y Procesos Estocásticos
        "siglas": "PPE",
        "profesores": [
            {"nombre": "Oriol Serra Albo", "rol": "Responsable (grupo 10)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Cuestionarios quincenales", "tipo": "otro", "porcentaje": 10},
                {"nombre": "Exámenes parciales", "tipo": "parcial", "porcentaje": 40},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 50},
            ]},
        ],
    },
    15: {  # Señales y Sistemas
        "siglas": "SST",
        "profesores": [
            {"nombre": "Francisco Vallverdu Bayes", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Joan Manuel Gene Bernaus", "rol": "Grupos 11, 12"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Control a mitad de curso", "tipo": "parcial", "porcentaje": 30},
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 10},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
        ],
    },
    16: {  # Diseño Digital
        "siglas": "DD",
        "profesores": [
            {"nombre": "Diego Cesar Mateo Peña", "rol": "Responsable (grupos 11, 12, 13, 14)"},
            {"nombre": "Daniel Bardes Llorensi", "rol": "Grupo 11"},
            {"nombre": "Jordi Cosp Vilella", "rol": "Grupo 12"},
            {"nombre": "Isidro Martin Garcia", "rol": "Grupo 13"},
            {"nombre": "Kristel Michelle Cedeño Mata", "rol": "Grupo 14"},
            {"nombre": "Joan Pons Nin", "rol": "Grupos 11, 12, 13, 14"},
        ],
        # Aproximación estructurada de una fórmula más matizada (ver guía docente
        # 230911): si la nota de control/actividades es menor que la del examen,
        # este pasa a valer el 100% de la parte de teoría.
        "esquemas": [
            {"nombre": "Teoría con control y actividades", "componentes": [
                {"nombre": "Control y actividades de teoría", "tipo": "parcial", "porcentaje": 18},
                {"nombre": "Examen final de teoría", "tipo": "examen_final", "porcentaje": 42},
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 40},
            ]},
            {"nombre": "Teoría solo examen final", "componentes": [
                {"nombre": "Examen final de teoría", "tipo": "examen_final", "porcentaje": 60},
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 40},
            ]},
        ],
    },
}


def ejecutar(database_uri=None, documentos_dir=None):
    from app import create_app
    from models import db, Asignatura, Profesor, EsquemaEvaluacion, ComponenteEvaluacion

    app = create_app(auto_seed=False, database_uri=database_uri, documentos_dir=documentos_dir)
    with app.app_context():
        for asignatura_id, datos in DATOS.items():
            asignatura = Asignatura.query.get(asignatura_id)
            if asignatura is None:
                print(f"AVISO: asignatura {asignatura_id} no existe, se omite")
                continue

            if not asignatura.siglas:
                asignatura.siglas = datos["siglas"]

            Profesor.query.filter_by(asignatura_id=asignatura_id).delete()
            for i, p in enumerate(datos["profesores"]):
                db.session.add(Profesor(
                    asignatura_id=asignatura_id, nombre=p["nombre"], rol=p.get("rol"), orden=i,
                ))

            EsquemaEvaluacion.query.filter_by(asignatura_id=asignatura_id).delete()
            for i, esquema_datos in enumerate(datos["esquemas"]):
                esquema = EsquemaEvaluacion(asignatura_id=asignatura_id, nombre=esquema_datos["nombre"], orden=i)
                db.session.add(esquema)
                db.session.flush()
                for c in esquema_datos["componentes"]:
                    db.session.add(ComponenteEvaluacion(
                        asignatura_id=asignatura_id, esquema_id=esquema.id,
                        nombre=c["nombre"], tipo=c["tipo"], porcentaje=c["porcentaje"],
                    ))

            print(f"asignatura {asignatura_id} ({asignatura.nombre}): "
                  f"{len(datos['profesores'])} profesores, {len(datos['esquemas'])} esquema(s)")

        db.session.commit()
        print("Carga de guías docentes completada.")


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
