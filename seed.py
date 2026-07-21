"""
Script de seed inicial para GREELEC (UPC/ETSETB).

Carga los 4 años / 8 cuatrimestres con las asignaturas reales del plan de estudios
(`plan_estudios_GREELEC.md`) y el estado de progreso descrito en ese mismo documento.

Estado real (confirmado por Dani, julio 2026):
- Cuatrimestres 1 y 2: superados por completo.
- Cuatrimestre 3: superado salvo Diseño Digital, que ahora está en curso (ver abajo).
- Cuatrimestre 5: empieza en septiembre de 2026 (todas sus obligatorias en "cursando"
  salvo Circuitos de Alta Frecuencia, que sigue "pendiente" hasta superar su
  prerrequisito). Diseño Digital (pendiente del 3º) se cursa en paralelo con el 5º,
  por eso pasa a "cursando" también.
- Cuatrimestre 4: empieza en febrero de 2027, todavía "pendiente" por completo.
- Cuatrimestres 6, 7 y 8: "pendiente", sin empezar.

Si tu situación real cambia, ajusta los estados con las rutas
PUT /cuatrimestres/<id> y PUT /asignaturas/<id>, y actualiza también este seed
para que un futuro reseed no lo revierta.

IDEMPOTENCIA (Fase 11): tanto `poblar_datos_iniciales()` como `python seed.py` (sin
--reset) son "get or create": si una asignatura ya existe (mismo nombre dentro del
mismo cuatrimestre), no se vuelve a crear ni se sobrescriben sus campos editables
(estado, nota_final, notas, metadatos de contacto...), que pueden llevar cambios
manuales desde la última vez que se sembró. Ejecutar el seed varias veces es seguro.

Uso:
  python seed.py           -> aplica migraciones pendientes y siembra lo que falte,
                               sin borrar nada (seguro para repetir).
  python seed.py --reset   -> BORRA y recrea la base de datos desde cero (todo se pierde).
                               Solo para desarrollo/pruebas, nunca sobre datos reales.

`poblar_datos_iniciales()` (siempre no-destructiva) es también la que usa la app
empaquetada (escritorio.py / app.py) para autocompletar la base de datos la primera
vez que se ejecuta el .exe, ya que en ese contexto no hay terminal desde la que
lanzar este script a mano.

SIGLAS (Fase Calendario/Horario, punto 11): `crear_asignatura()` acepta un parámetro
`siglas` opcional y, si se pasa, localiza por siglas antes que por nombre+cuatrimestre
(son únicas en toda la BD). Ninguna asignatura de este seed lleva siglas todavía: no
son un dato inventable, son el código oficial del plan de estudios de la UPC/ETSETB, y
la spec pide explícitamente no inventarlos. Usa `informe_siglas.py` para ver qué
asignaturas siguen sin siglas y añádelas tú a mano (por la interfaz o pasando
`siglas="..."` aquí) cuando tengas el código real de cada una.
"""

import sys

from flask_migrate import stamp as sellar_migraciones, upgrade as aplicar_migraciones

from app import create_app
from models import db, Anio, Cuatrimestre, Asignatura, RecursoExterno
from utils import crear_apartados_por_defecto


def obtener_o_crear_anio(numero):
    anio = Anio.query.filter_by(numero=numero).first()
    if anio:
        return anio
    anio = Anio(numero=numero)
    db.session.add(anio)
    db.session.flush()
    return anio


def obtener_o_crear_cuatrimestre(anio, numero, estado):
    cuatrimestre = Cuatrimestre.query.filter_by(numero=numero).first()
    if cuatrimestre:
        return cuatrimestre
    cuatrimestre = Cuatrimestre(anio_id=anio.id, numero=numero, estado=estado)
    db.session.add(cuatrimestre)
    db.session.flush()
    return cuatrimestre


def crear_asignatura(cuatrimestre, nombre, ects, tipo="obligatoria", estado="pendiente",
                      nota_final=None, origen_catalogo=False, siglas=None,
                      despacho_profesor=None, correo_profesor=None, link_aula_virtual=None,
                      recursos_externos=None):
    """
    Idempotente ("obtener o crear"): si ya existe la asignatura, se devuelve tal cual,
    sin tocar ninguno de sus campos (puede llevar ediciones manuales desde el último
    seed, incluidas unas siglas puestas a mano desde la interfaz). Solo en la creación
    inicial se rellenan los metadatos, se crean los apartados por defecto y los
    recursos externos dados.

    Localización (spec Fase Calendario/Horario punto 11 — "localizar preferentemente
    mediante siglas"): si se pasan `siglas`, se busca primero por ellas (son únicas en
    toda la BD, a diferencia del nombre que solo es único dentro de un cuatrimestre);
    si no hay coincidencia — o no se pasaron siglas —, se cae al criterio de siempre
    (nombre + cuatrimestre).
    """
    asignatura = None
    if siglas:
        asignatura = Asignatura.query.filter_by(siglas=siglas.strip().upper()).first()
    if asignatura is None:
        asignatura = Asignatura.query.filter_by(cuatrimestre_id=cuatrimestre.id, nombre=nombre).first()
    if asignatura:
        return asignatura

    asignatura = Asignatura(
        cuatrimestre_id=cuatrimestre.id,
        nombre=nombre,
        siglas=siglas,
        creditos_ects=ects,
        tipo=tipo,
        estado=estado,
        nota_final=nota_final,
        origen_catalogo=origen_catalogo,
        despacho_profesor=despacho_profesor,
        correo_profesor=correo_profesor,
        link_aula_virtual=link_aula_virtual,
    )
    db.session.add(asignatura)
    db.session.flush()
    crear_apartados_por_defecto(asignatura)

    for recurso in (recursos_externos or []):
        db.session.add(RecursoExterno(
            asignatura_id=asignatura.id,
            nombre=recurso["nombre"],
            url=recurso["url"],
            tipo=recurso.get("tipo"),
        ))

    return asignatura


def obligatorias(cuatrimestre, nombres_ects, estado):
    """nombres_ects: lista de tuplas (nombre, ects). Crea (o recupera) todas con el mismo estado."""
    creadas = {}
    for nombre, ects in nombres_ects:
        creadas[nombre] = crear_asignatura(cuatrimestre, nombre, ects, tipo="obligatoria", estado=estado)
    return creadas


def catalogo_optativas(cuatrimestre, nombres_ects):
    """Carga (o recupera) el catálogo de optativas de un cuatrimestre: todas en estado no_elegida."""
    for nombre, ects in nombres_ects:
        crear_asignatura(
            cuatrimestre, nombre, ects, tipo="optativa", estado="no_elegida", origen_catalogo=True
        )


def _asignar_prerrequisitos_si_no_tiene(asignatura, prerrequisitos):
    """Solo fija prerrequisitos si la asignatura no tiene ninguno ya asignado, para no
    pisar un cambio manual (p. ej. si alguien los quitó a propósito vía la API)."""
    if not asignatura.prerrequisitos:
        asignatura.prerrequisitos = prerrequisitos


def poblar_datos_iniciales():
    """Puebla las tablas con los datos reales de GREELEC. Idempotente: no duplica ni
    sobrescribe asignaturas/recursos ya existentes. Asume que las tablas ya existen
    (migradas) y que hay un app_context activo."""
    # ---------- AÑO 1 ----------
    anio1 = obtener_o_crear_anio(1)

    c1 = obtener_o_crear_cuatrimestre(anio1, 1, estado="superado")
    obligatorias(c1, [
        ("Álgebra Lineal", 6),
        ("Algoritmia y Programación", 6),
        ("Cálculo", 6),
        ("Componentes y Circuitos Electrónicos", 6),
        ("Física", 6),
    ], estado="superada")

    # En realidad es optativa (corregido julio 2026): tiene el mismo flujo de
    # elección que las demás optativas del catálogo, con estado no_elegida por
    # defecto hasta que se decida manualmente si se cursó o no.
    catalogo_optativas(c1, [
        ("Introducción a las Matemáticas y a la Ingeniería de las Telecomunicaciones", 3),
    ])

    c2 = obtener_o_crear_cuatrimestre(anio1, 2, estado="superado")
    obligatorias(c2, [
        ("Análisis de Circuitos", 6),
        ("Cálculo Vectorial", 6),
        ("Ecuaciones Diferenciales y Transformadas", 6),
        ("Electromagnetismo", 6),
        ("Programación y Estructuras de Datos", 6),
    ], estado="superada")

    # ---------- AÑO 2 ----------
    anio2 = obtener_o_crear_anio(2)

    # 3er cuatrimestre: superado salvo Diseño Digital (pendiente) -> cuatrimestre "actual"
    c3 = obtener_o_crear_cuatrimestre(anio2, 3, estado="actual")
    obligatorias(c3, [
        ("Dispositivos Electrónicos", 6),
        ("Electromagnetismo Aplicado y Fotónica", 6),
        ("Probabilidad y Procesos Estocásticos", 6),
        ("Señales y Sistemas", 6),
    ], estado="superada")
    # Pendiente del 3º, pero se cursa en paralelo con el 5º (septiembre 2026)
    crear_asignatura(c3, "Diseño Digital", 6, tipo="obligatoria", estado="cursando")

    catalogo_optativas(c3, [
        ("Administración de Sistemas Linux", 2),
        ("Álgebra Lineal, Códigos Lineales y Esquemas de Compartición de Secretos", 2),
        ("Crear Tu Futuro: un Simple Trabajo o Tu Auténtica Pasión", 2),
        ("Ética para la Ingeniería", 2),
        ("La Ingeniería Financiera en la Planificación Económica de Inversiones", 2),
        ("Liderazgo y Técnicas de Desarrollo Profesional en la Ingeniería", 2),
        ("Proyecto de Cooperación con Tecnologías WiFi", 2),
        ("Simulación y Análisis de Circuitos mediante PSpice", 2),
    ])

    c4 = obtener_o_crear_cuatrimestre(anio2, 4, estado="pendiente")
    asig_c4 = obligatorias(c4, [
        ("Circuitos Analógicos", 6),
        ("Empresa y Proyectos", 6),
        ("Introducción a los Circuitos de Alta Frecuencia", 6),
        ("Sistemas Embebidos", 6),
        ("Tratamiento de la Señal", 6),
    ], estado="pendiente")

    # ---------- AÑO 3 ----------
    anio3 = obtener_o_crear_anio(3)

    # Empieza en septiembre 2026 -> cuatrimestre "actual"
    c5 = obtener_o_crear_cuatrimestre(anio3, 5, estado="actual")
    asig_c5 = obligatorias(c5, [
        ("Ciencia e Ingeniería de Materiales", 6),
        ("Sistemas de Control", 6),
        ("Sistemas de Medida", 6),
        ("Sistemas Digitales Configurables", 6),
    ], estado="cursando")

    # Circuitos de Alta Frecuencia se pospone: requiere haber superado antes
    # Introducción a los Circuitos de Alta Frecuencia (4º cuatrimestre, aún pendiente)
    asig_c5["Circuitos de Alta Frecuencia"] = crear_asignatura(
        c5, "Circuitos de Alta Frecuencia", 6, tipo="obligatoria", estado="pendiente"
    )
    _asignar_prerrequisitos_si_no_tiene(
        asig_c5["Circuitos de Alta Frecuencia"],
        [asig_c4["Introducción a los Circuitos de Alta Frecuencia"]],
    )

    catalogo_optativas(c5, [
        ("Aprendizaje Automático: de la Teoría a la Práctica", 2),
        ("Introducción al Aprendizaje Profundo", 2),
        ("Resolución de Problemas con Inteligencia Artificial: un Enfoque Práctico", 2),
    ])

    c6 = obtener_o_crear_cuatrimestre(anio3, 6, estado="pendiente")
    obligatorias(c6, [
        ("Internet de las Cosas", 6),
        ("Procesado de la Energía Eléctrica", 6),
        ("Sistemas en Tiempo Real", 6),
        ("Técnicas para el Emprendimiento", 6),
        ("Tecnología Electrónica", 6),
    ], estado="pendiente")

    catalogo_optativas(c6, [
        ("Sistemas Electrónicos en Automoción", 2),
    ])

    # ---------- AÑO 4 ----------
    anio4 = obtener_o_crear_anio(4)

    # 7º cuatrimestre: alto grado de optatividad -> todo catálogo, se elige el perfil
    c7 = obtener_o_crear_cuatrimestre(anio4, 7, estado="pendiente")
    catalogo_optativas(c7, [
        ("Diseño Microelectrónico", 6),
        ("Integración de Sistemas", 12),
        ("Sistemas de Hardware de Procesado de la Información", 6),
        ("Telecomunicación Espacial", 6),
        ("Sensores, Actuadores y Microcontroladores en Robots Móviles", 6),
        ("Aprendizaje por Refuerzo y Aprendizaje Profundo", 6),
        ("Dispositivos Fotovoltaicos", 6),
        ("Electrónica Inteligente", 6),
        ("Matlab y sus Aplicaciones en Ingeniería", 6),
        ("Seguridad y Privacidad de la Información", 6),
    ])

    c8 = obtener_o_crear_cuatrimestre(anio4, 8, estado="pendiente")
    crear_asignatura(c8, "Trabajo de Fin de Grado", 18, tipo="obligatoria", estado="pendiente")

    db.session.commit()

    from models import Apartado
    total_asignaturas = Asignatura.query.count()
    total_apartados = Apartado.query.count()
    print(f"Seed completado: {total_asignaturas} asignaturas en la base "
          f"(incluye catálogo de optativas en estado no_elegida), "
          f"{total_apartados} apartados en total.")


def seed(reset=False):
    """
    Punto de entrada manual (`python seed.py`).

    Por defecto (reset=False): NO destructivo. Aplica las migraciones pendientes y
    siembra lo que falte sin tocar nada existente; seguro de ejecutar tantas veces
    como se quiera.

    Con reset=True (`python seed.py --reset`): BORRA la base de datos y la recrea
    desde cero con el esquema actual. Solo pensado para desarrollo/pruebas locales;
    jamás debe usarse sobre una base de datos con datos reales sin backup previo.
    """
    app = create_app(auto_seed=False)
    with app.app_context():
        if reset:
            db.drop_all()
            db.create_all()
            sellar_migraciones()  # tablas creadas a mano con el esquema actual: marcar como ya migradas
        else:
            aplicar_migraciones()
        poblar_datos_iniciales()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
