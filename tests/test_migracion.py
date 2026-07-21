from flask_migrate import downgrade, upgrade

from config import MIGRATIONS_DIR
from models import Asignatura, Apartado

# Revisión justo anterior a la de "esquemas de evaluación alternativos". Se referencia
# por id explícito (no con revision="-1") porque los tests de esa migración necesitan
# bajar justo hasta ahí, y "-1" dejaría de apuntar ahí en cuanto se añadiera cualquier
# migración posterior (como pasó al añadir la de calendario/horario).
REV_ANTES_DE_ESQUEMAS = "41e04bad8c03"


def test_migracion_conserva_datos_existentes(app_vacia):
    from seed import poblar_datos_iniciales

    with app_vacia.app_context():
        poblar_datos_iniciales()

        total_asignaturas_antes = Asignatura.query.count()
        total_apartados_antes = Apartado.query.count()
        muestra_antes = Asignatura.query.filter_by(nombre="Diseño Digital").first()
        estado_muestra = muestra_antes.estado
        assert total_asignaturas_antes == 54

        # Retrocede una migración y vuelve a subir: las filas ya guardadas deben sobrevivir
        # al ciclo completo de downgrade/upgrade (comprueba que ninguna migración borra datos).
        downgrade(directory=MIGRATIONS_DIR, revision="-1")
        upgrade(directory=MIGRATIONS_DIR)

        total_asignaturas_despues = Asignatura.query.count()
        total_apartados_despues = Apartado.query.count()
        muestra_despues = Asignatura.query.filter_by(nombre="Diseño Digital").first()

        assert total_asignaturas_despues == total_asignaturas_antes
        assert total_apartados_despues == total_apartados_antes
        assert muestra_despues.estado == estado_muestra


def test_migracion_esquemas_backfill_conserva_notas(app_vacia):
    """
    Regresión: migrar una base que YA tenía componentes de evaluación con nota.

    El backfill que los agrupa en un "Esquema único" solo se ejecuta cuando existen
    componentes previos, así que este camino no lo cubría ningún test (todos partían
    de una base recién creada, sin componentes) y llegó roto al .exe.
    """
    from models import db, Asignatura, ComponenteEvaluacion, EsquemaEvaluacion
    from seed import poblar_datos_iniciales

    with app_vacia.app_context():
        poblar_datos_iniciales()
        asignatura = Asignatura.query.filter_by(nombre="Diseño Digital").first()

        # Retrocede por debajo de la migración de esquemas y deja componentes "sueltos",
        # tal como estaban antes de que existieran los EsquemaEvaluacion.
        downgrade(directory=MIGRATIONS_DIR, revision=REV_ANTES_DE_ESQUEMAS)
        db.session.execute(
            db.text(
                "INSERT INTO componente_evaluacion (asignatura_id, nombre, tipo, porcentaje, nota) "
                "VALUES (:aid, 'Parcial', 'parcial', 40, 7.5), (:aid, 'Final', 'examen_final', 60, 4.25)"
            ),
            {"aid": asignatura.id},
        )
        db.session.commit()

        upgrade(directory=MIGRATIONS_DIR)

        esquemas = EsquemaEvaluacion.query.filter_by(asignatura_id=asignatura.id).all()
        assert len(esquemas) == 1, "los componentes sueltos deben acabar en un único esquema"

        componentes = ComponenteEvaluacion.query.filter_by(asignatura_id=asignatura.id).all()
        assert len(componentes) == 2
        assert all(c.esquema_id == esquemas[0].id for c in componentes)
        # Lo importante: ninguna nota ya introducida se pierde por el camino.
        assert sorted(c.nota for c in componentes) == [4.25, 7.5]


def test_migracion_esquemas_es_reentrante_tras_interrupcion(app_vacia):
    """
    Regresión: en SQLite el DDL hace auto-commit, así que una migración interrumpida
    (p. ej. el .exe cerrándose a media actualización) deja restos —incluida la tabla
    temporal de batch_alter_table— y el reintento debe poder completarla igualmente,
    en vez de fallar para siempre con "table ... already exists".
    """
    from models import db, EsquemaEvaluacion

    with app_vacia.app_context():
        downgrade(directory=MIGRATIONS_DIR, revision=REV_ANTES_DE_ESQUEMAS)

        # Simula el estado que deja una interrupción a mitad de la migración.
        db.session.execute(db.text(
            "CREATE TABLE esquema_evaluacion ("
            "id INTEGER NOT NULL PRIMARY KEY, asignatura_id INTEGER NOT NULL, "
            "nombre VARCHAR(200) NOT NULL, orden INTEGER NOT NULL)"
        ))
        db.session.execute(db.text(
            "CREATE TABLE _alembic_tmp_componente_evaluacion (id INTEGER NOT NULL PRIMARY KEY)"
        ))
        db.session.commit()

        upgrade(directory=MIGRATIONS_DIR)  # no debe lanzar

        tablas = set(inspect_tablas(db))
        assert "esquema_evaluacion" in tablas
        assert "_alembic_tmp_componente_evaluacion" not in tablas, "el resto temporal debe limpiarse"
        assert EsquemaEvaluacion.query.count() == 0  # no había componentes que migrar


def inspect_tablas(db):
    from sqlalchemy import inspect
    return inspect(db.engine).get_table_names()


def test_esquema_completo_se_construye_desde_vacio(app_vacia):
    """El upgrade ya se aplicó al crear la app (create_app llama a aplicar_migraciones);
    esto solo confirma que las tablas de todas las fases quedaron creadas."""
    from sqlalchemy import inspect
    from models import db

    with app_vacia.app_context():
        tablas = set(inspect(db.engine).get_table_names())
        esperadas = {
            "anio", "cuatrimestre", "asignatura", "componente_evaluacion", "apartado",
            "documento", "marcador", "tarea_evento", "configuracion_app", "pagina_texto",
            "hito", "concepto", "recurso_externo", "esquema_evaluacion", "horario_clase",
        }
        assert esperadas.issubset(tablas)
