# -*- coding: utf-8 -*-
"""
Continuación de cargar_guias_docentes.py: siglas, profesorado y esquemas de
evaluación para las 38 asignaturas restantes (obligatorias de 4º-6º cuatrimestre
y optativas de 3º-7º), extraídos de las guías docentes oficiales de la UPC
(https://www.upc.edu/content/grau/guiadocent/pdf/esp/<codigo>/<slug>.pdf).

Varias guías de cuatrimestres futuros no tienen profesorado publicado todavía
("Profesorado responsable:" vacío): en esos casos la lista de profesores queda
vacía a propósito, no se inventa nadie.

Uso:
    python cargar_guias_docentes_2.py --target dev
    python cargar_guias_docentes_2.py --target dist
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATOS = {
    6: {  # Introducción a las Matemáticas y a la Ingeniería de las Telecomunicaciones
        "siglas": "IMATEC",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Actividades y participación (mejorable con prueba final)", "tipo": "otro", "porcentaje": 100},
            ]},
        ],
    },
    17: {  # Administración de Sistemas Linux
        "siglas": "ADMINUX",
        "profesores": [
            {"nombre": "Jose Luis Muñoz Tapia", "rol": "Responsable (grupo 11)"},
            {"nombre": "Jorge Mata Diaz", "rol": "Grupo 11"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Tema 1", "tipo": "otro", "porcentaje": 40},
                {"nombre": "Tema 2", "tipo": "otro", "porcentaje": 20},
                {"nombre": "Tema 3", "tipo": "otro", "porcentaje": 20},
                {"nombre": "Tema 4", "tipo": "otro", "porcentaje": 20},
            ]},
        ],
    },
    18: {  # Álgebra Lineal, Códigos Lineales y Esquemas de Compartición de Secretos
        "siglas": "COMSECRET",
        "profesores": [
            {"nombre": "German Saez Moreno", "rol": "Responsable (grupo 10)"},
            {"nombre": "Francisco Javier Muñoz Lopez", "rol": "Grupo 10"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Actividades y participación (mejorable con control final)", "tipo": "otro", "porcentaje": 100},
            ]},
        ],
    },
    19: {  # Crear Tu Futuro: un Simple Trabajo o Tu Auténtica Pasión
        "siglas": "CTFUTUR",
        "profesores": [
            {"nombre": "Eva Maria Vidal Lopez", "rol": "Responsable (grupo 10)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Presentación pública de trabajo personal", "tipo": "otro", "porcentaje": 100},
            ]},
        ],
    },
    20: {  # Ética para la Ingeniería
        "siglas": "EE",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Participación y debates", "tipo": "otro", "porcentaje": 30},
                {"nombre": "Trabajos y actividades del curso", "tipo": "otro", "porcentaje": 30},
                {"nombre": "Presentación final de reflexión", "tipo": "otro", "porcentaje": 40},
            ]},
        ],
    },
    21: {  # La Ingeniería Financiera en la Planificación Económica de Inversiones
        "siglas": "EFPEI",
        "profesores": [],
        "esquemas": [],  # guía sin sistema de calificación publicado
    },
    22: {  # Liderazgo y Técnicas de Desarrollo Profesional en la Ingeniería
        "siglas": "LTDPE",
        "profesores": [
            {"nombre": "Francisco Torres Torres", "rol": "Responsable (grupo 10)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Trabajos prácticos y participación (sin examen final)", "tipo": "otro", "porcentaje": 100},
            ]},
        ],
    },
    23: {  # Proyecto de Cooperación con Tecnologías WiFi
        "siglas": "PROJICT4D",
        "profesores": [],
        "esquemas": [],  # guía sin sistema de calificación publicado
    },
    24: {  # Simulación y Análisis de Circuitos mediante PSpice
        "siglas": "PSPICE",
        "profesores": [
            {"nombre": "Antonio Turo Peroy", "rol": "Responsable (grupo 11)"},
            {"nombre": "Juan Antonio Chavez Dominguez", "rol": "Grupo 11"},
            {"nombre": "Santiago Silvestre Berges", "rol": "Grupo 11"},
        ],
        "esquemas": [
            {"nombre": "Evaluación (NF = (P2+P3+P4+2·P5+2·P6)/7)", "componentes": [
                {"nombre": "Práctica 2", "tipo": "laboratorio", "porcentaje": 14.29},
                {"nombre": "Práctica 3", "tipo": "laboratorio", "porcentaje": 14.29},
                {"nombre": "Práctica 4", "tipo": "laboratorio", "porcentaje": 14.28},
                {"nombre": "Práctica 5", "tipo": "laboratorio", "porcentaje": 28.57},
                {"nombre": "Práctica 6", "tipo": "laboratorio", "porcentaje": 28.57},
            ]},
        ],
    },
    25: {  # Circuitos Analógicos
        "siglas": "CA",
        "profesores": [],
        "esquemas": [
            {"nombre": "Con examen parcial", "componentes": [
                {"nombre": "Prácticas de laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Examen final de laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Examen parcial", "tipo": "parcial", "porcentaje": 20},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 40},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Prácticas de laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Examen final de laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
        ],
    },
    26: {  # Empresa y Proyectos
        "siglas": "EP",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Evaluación continua", "tipo": "otro", "porcentaje": 60},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 40},
            ]},
        ],
    },
    27: {  # Introducción a los Circuitos de Alta Frecuencia
        "siglas": "ICAF",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
                {"nombre": "Evaluación continuada", "tipo": "parcial", "porcentaje": 25},
                {"nombre": "Prácticas de laboratorio", "tipo": "laboratorio", "porcentaje": 15},
            ]},
        ],
    },
    28: {  # Sistemas Embebidos
        "siglas": "EMB",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 50},
                {"nombre": "Prácticas", "tipo": "laboratorio", "porcentaje": 30},
                {"nombre": "Evaluación continua", "tipo": "parcial", "porcentaje": 20},
            ]},
        ],
    },
    29: {  # Tratamiento de la Señal
        "siglas": "TRS",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Control", "tipo": "parcial", "porcentaje": 20},
                {"nombre": "Seguimiento de laboratorio", "tipo": "laboratorio", "porcentaje": 25},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 55},
            ]},
        ],
    },
    30: {  # Ciencia e Ingeniería de Materiales
        "siglas": "CEM",
        "profesores": [
            {"nombre": "Cristobal Voz Sanchez", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Gerard Masmitjà Rusiñol", "rol": "Grupos 11, 13"},
            {"nombre": "Joaquin Puigdollers Gonzalez", "rol": "Grupos 11, 12, 13"},
        ],
        "esquemas": [
            {"nombre": "Con control", "componentes": [
                {"nombre": "Control", "tipo": "parcial", "porcentaje": 30},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 50},
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 20},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 80},
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 20},
            ]},
        ],
    },
    31: {  # Sistemas de Control
        "siglas": "CTR",
        "profesores": [
            {"nombre": "Domingo Biel Sole", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Manuel Maria Dominguez Pumar", "rol": "Grupos 11, 12, 13"},
        ],
        "esquemas": [
            {"nombre": "Con examen parcial", "componentes": [
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Examen parcial", "tipo": "parcial", "porcentaje": 28},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 52},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 80},
            ]},
        ],
    },
    32: {  # Sistemas de Medida
        "siglas": "SM",
        "profesores": [
            {"nombre": "Miquel Angel Garcia Gonzalez", "rol": "Responsable (grupos 11, 12, 13)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 40},
                {"nombre": "Evaluación continuada", "tipo": "parcial", "porcentaje": 25},
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 35},
            ]},
        ],
    },
    33: {  # Sistemas Digitales Configurables
        "siglas": "SDC",
        "profesores": [
            {"nombre": "Joan Pons Nin", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Juan Antonio Chavez Dominguez", "rol": "Grupos 11, 12, 13"},
        ],
        "esquemas": [
            {"nombre": "Teoría con evaluación continua", "componentes": [
                {"nombre": "Evaluación continua de teoría", "tipo": "parcial", "porcentaje": 25},
                {"nombre": "Examen final de teoría", "tipo": "examen_final", "porcentaje": 25},
                {"nombre": "Evaluación continua de laboratorio", "tipo": "laboratorio", "porcentaje": 37.5},
                {"nombre": "Examen final de laboratorio", "tipo": "laboratorio", "porcentaje": 12.5},
            ]},
            {"nombre": "Teoría solo examen final", "componentes": [
                {"nombre": "Examen final de teoría", "tipo": "examen_final", "porcentaje": 50},
                {"nombre": "Evaluación continua de laboratorio", "tipo": "laboratorio", "porcentaje": 37.5},
                {"nombre": "Examen final de laboratorio", "tipo": "laboratorio", "porcentaje": 12.5},
            ]},
        ],
    },
    34: {  # Circuitos de Alta Frecuencia
        "siglas": "CIAF",
        "profesores": [
            {"nombre": "Jordi Joan Mallorqui Franquet", "rol": "Responsable (grupos 11, 12, 13)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Controles", "tipo": "parcial", "porcentaje": 15},
                {"nombre": "Prácticas de ordenador y laboratorio", "tipo": "laboratorio", "porcentaje": 25},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
        ],
    },
    35: {  # Aprendizaje Automático: de la Teoría a la Práctica
        "siglas": "APATP",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Cuestionarios", "tipo": "otro", "porcentaje": 50},
                {"nombre": "Competición", "tipo": "otro", "porcentaje": 50},
            ]},
        ],
    },
    36: {  # Introducción al Aprendizaje Profundo
        "siglas": "IDL",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 100},
            ]},
        ],
    },
    37: {  # Resolución de Problemas con Inteligencia Artificial: un Enfoque Práctico
        "siglas": "AIPRAC",
        "profesores": [
            {"nombre": "Enrique Monte Moreno", "rol": "Responsable (grupo 11)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Notebook entregado por sesión", "tipo": "laboratorio", "porcentaje": 100},
            ]},
        ],
    },
    38: {  # Internet de las Cosas
        "siglas": "IOT",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Controles de teoría", "tipo": "parcial", "porcentaje": 60},
                {"nombre": "Pruebas de laboratorio", "tipo": "laboratorio", "porcentaje": 34},
                {"nombre": "Memorias de prácticas", "tipo": "laboratorio", "porcentaje": 6},
            ]},
        ],
    },
    39: {  # Procesado de la Energía Eléctrica
        "siglas": "PEE",
        "profesores": [],
        "esquemas": [
            {"nombre": "Con examen parcial", "componentes": [
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Examen parcial", "tipo": "parcial", "porcentaje": 30.4},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 49.6},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 20},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 80},
            ]},
        ],
    },
    40: {  # Sistemas en Tiempo Real
        "siglas": "RT",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Control", "tipo": "parcial", "porcentaje": 30},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 30},
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 40},
            ]},
        ],
    },
    41: {  # Técnicas para el Emprendimiento
        "siglas": "TEM",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Controles", "tipo": "parcial", "porcentaje": 40},
                {"nombre": "Proyecto", "tipo": "otro", "porcentaje": 60},
            ]},
        ],
    },
    42: {  # Tecnología Electrónica
        "siglas": "TEL",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 40},
                {"nombre": "Prácticas", "tipo": "laboratorio", "porcentaje": 35},
                {"nombre": "Evaluación continua", "tipo": "parcial", "porcentaje": 25},
            ]},
        ],
    },
    43: {  # Sistemas Electrónicos en Automoción
        "siglas": "ELEAUTO",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Informes de trabajos", "tipo": "otro", "porcentaje": 70},
                {"nombre": "Presentaciones orales", "tipo": "otro", "porcentaje": 30},
            ]},
        ],
    },
    44: {  # Diseño Microelectrónico
        "siglas": "DMIC",
        "profesores": [
            {"nombre": "Diego Cesar Mateo Peña", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Xavier Aragones Cervera", "rol": "Grupos 11, 12, 13"},
            {"nombre": "Josep Altet Sanahujes", "rol": "Grupo 13"},
        ],
        "esquemas": [
            {"nombre": "Con evaluación continuada", "componentes": [
                {"nombre": "Prácticas de laboratorio", "tipo": "laboratorio", "porcentaje": 40},
                {"nombre": "Evaluación continuada", "tipo": "parcial", "porcentaje": 20},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 40},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Prácticas de laboratorio", "tipo": "laboratorio", "porcentaje": 40},
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 60},
            ]},
        ],
    },
    45: {  # Integración de Sistemas
        "siglas": "INT",
        "profesores": [
            {"nombre": "Ramon Bragos Bardia", "rol": "Responsable"},
        ],
        "esquemas": [],  # evaluación por rúbrica de proyecto, sin desglose porcentual
    },
    46: {  # Sistemas de Hardware de Procesado de la Información
        "siglas": "HIPS",
        "profesores": [
            {"nombre": "Jordi Madrenas Boadas", "rol": "Responsable (grupos 11, 12, 13)"},
            {"nombre": "Juan Manuel Moreno Arostegui", "rol": "Grupo 12"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 40},
                {"nombre": "Prácticas", "tipo": "laboratorio", "porcentaje": 40},
                {"nombre": "Examen parcial", "tipo": "parcial", "porcentaje": 20},
            ]},
        ],
    },
    47: {  # Telecomunicación Espacial
        "siglas": "TELESP",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 50},
                {"nombre": "Examen parcial", "tipo": "parcial", "porcentaje": 30},
                {"nombre": "Sesiones prácticas y actividades", "tipo": "laboratorio", "porcentaje": 20},
            ]},
        ],
    },
    48: {  # Sensores, Actuadores y Microcontroladores en Robots Móviles
        "siglas": "SAM",
        "profesores": [
            {"nombre": "Sergio Bermejo Sanchez", "rol": "Responsable (grupo 11)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Mini-proyectos robóticos guiados", "tipo": "otro", "porcentaje": 100},
            ]},
        ],
    },
    49: {  # Aprendizaje por Refuerzo y Aprendizaje Profundo
        "siglas": "ARAP",
        "profesores": [
            {"nombre": "Jose Vidal Manzano", "rol": "Responsable (grupos 11, 13)"},
            {"nombre": "Antonio Jesus Bonafonte Cavez", "rol": "Grupos 11, 13"},
            {"nombre": "Margarita Asuncion Cabrera Bean", "rol": "Grupos 11, 13"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Exámenes y evaluación en prácticas", "tipo": "otro", "porcentaje": 100},
            ]},
        ],
    },
    50: {  # Dispositivos Fotovoltaicos
        "siglas": "DIFO",
        "profesores": [],
        "esquemas": [
            {"nombre": "Con controles", "componentes": [
                {"nombre": "Control 1", "tipo": "parcial", "porcentaje": 45},
                {"nombre": "Control 2", "tipo": "parcial", "porcentaje": 25},
                {"nombre": "Problemas y actividades", "tipo": "otro", "porcentaje": 5},
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 25},
            ]},
            {"nombre": "Solo examen final", "componentes": [
                {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 75},
                {"nombre": "Laboratorio", "tipo": "laboratorio", "porcentaje": 25},
            ]},
        ],
    },
    51: {  # Electrónica Inteligente
        "siglas": "EI",
        "profesores": [
            {"nombre": "Sergio Bermejo Sanchez", "rol": "Responsable (grupo 11)"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Trabajo teórico", "tipo": "teoria", "porcentaje": 20},
                {"nombre": "Ejercicios", "tipo": "otro", "porcentaje": 30},
                {"nombre": "Trabajo práctico", "tipo": "laboratorio", "porcentaje": 50},
            ]},
        ],
    },
    52: {  # Matlab y sus Aplicaciones en Ingeniería
        "siglas": "MAE",
        "profesores": [
            {"nombre": "Jorge Luis Villar Santos", "rol": "Responsable (grupos 11, 13)"},
            {"nombre": "Javier Rodriguez Fonollosa", "rol": "Grupos 11, 13"},
        ],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Parte I (ejercicios)", "tipo": "otro", "porcentaje": 30},
                {"nombre": "Parte II (trabajo final)", "tipo": "otro", "porcentaje": 70},
            ]},
        ],
    },
    53: {  # Seguridad y Privacidad de la Información
        "siglas": "SPI",
        "profesores": [],
        "esquemas": [
            {"nombre": "Evaluación", "componentes": [
                {"nombre": "Controles", "tipo": "parcial", "porcentaje": 50},
                {"nombre": "Participación activa en clase", "tipo": "otro", "porcentaje": 20},
                {"nombre": "Trabajos y presentaciones", "tipo": "otro", "porcentaje": 30},
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
        print("Carga de guías docentes (parte 2) completada.")


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
