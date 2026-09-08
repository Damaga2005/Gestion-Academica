import os

from flask import Flask, jsonify, redirect, url_for
from flask_migrate import Migrate, upgrade as aplicar_migraciones

from config import Config, RESOURCE_DIR, MIGRATIONS_DIR
from models import db
from routes.errors import register_error_handlers
from routes.anios import anios_bp
from routes.cuatrimestres import cuatrimestres_bp
from routes.asignaturas import asignaturas_bp
from routes.componentes import componentes_bp
from routes.esquemas import esquemas_bp
from routes.apartados import apartados_bp
from routes.grupos_documento import grupos_documento_bp
from routes.documentos import documentos_bp
from routes.marcadores import marcadores_bp
from routes.anotaciones import anotaciones_bp
from routes.tareas import tareas_bp
from routes.espacios_estudio import espacios_estudio_bp
from routes.conflictos import conflictos_bp
from routes.horarios import horarios_bp
from routes.ics import ics_bp
from routes.configuracion import configuracion_bp, obtener_configuracion
from routes.backup import backup_bp
from routes.busqueda import busqueda_bp
from routes.notificaciones import notificaciones_bp
from routes.racha import racha_bp
from routes.notas_rapidas import notas_rapidas_bp
from routes.hitos import hitos_bp
from routes.conceptos import conceptos_bp
from routes.recursos_externos import recursos_externos_bp
from routes.profesores import profesores_bp
from routes.guia_docente import guia_docente_bp
from routes.auth import auth_bp, registrar_gate_autenticacion, registrar_csrf_global
from routes.vistas import vistas_bp

migrate = Migrate()


def _bootstrap_datos_iniciales_si_vacio():
    """
    Autocompleta la base de datos con el seed real la primera vez que se arranca
    (p. ej. al abrir el .exe empaquetado, donde no hay terminal para lanzar seed.py
    a mano). Si ya hay algún Año creado, no toca nada.

    Defensivo ante bases de datos sin migrar todavía (p. ej. herramientas de Alembic
    operando sobre un esquema aún vacío): si la tabla ni siquiera existe, no hay nada
    que comprobar ni sembrar todavía.
    """
    from sqlalchemy import inspect

    from models import Anio
    from seed import poblar_datos_iniciales

    if not inspect(db.engine).has_table("anio"):
        return
    if Anio.query.count() == 0:
        poblar_datos_iniciales()


def create_app(auto_seed=True, database_uri=None, documentos_dir=None):
    """
    database_uri / documentos_dir: overrides usados solo por los tests, para apuntar a
    una base de datos y carpeta de documentos temporales en vez de a las del proyecto
    real. En uso normal (CLI, escritorio) se dejan en None y se usan los de Config.
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(RESOURCE_DIR, "templates"),
        static_folder=os.path.join(RESOURCE_DIR, "static"),
    )
    app.config.from_object(Config)
    if database_uri:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    if documentos_dir:
        app.config["DOCUMENTOS_DIR"] = documentos_dir

    db.init_app(app)
    migrate.init_app(app, db, directory=MIGRATIONS_DIR)
    register_error_handlers(app)

    app.register_blueprint(anios_bp)
    app.register_blueprint(cuatrimestres_bp)
    app.register_blueprint(asignaturas_bp)
    app.register_blueprint(componentes_bp)
    app.register_blueprint(esquemas_bp)
    app.register_blueprint(apartados_bp)
    app.register_blueprint(grupos_documento_bp)
    app.register_blueprint(documentos_bp)
    app.register_blueprint(marcadores_bp)
    app.register_blueprint(anotaciones_bp)
    app.register_blueprint(tareas_bp)
    app.register_blueprint(espacios_estudio_bp)
    app.register_blueprint(conflictos_bp)
    app.register_blueprint(horarios_bp)
    app.register_blueprint(ics_bp)
    app.register_blueprint(configuracion_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(busqueda_bp)
    app.register_blueprint(notificaciones_bp)
    app.register_blueprint(racha_bp)
    app.register_blueprint(notas_rapidas_bp)
    app.register_blueprint(hitos_bp)
    app.register_blueprint(conceptos_bp)
    app.register_blueprint(recursos_externos_bp)
    app.register_blueprint(profesores_bp)
    app.register_blueprint(guia_docente_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(vistas_bp)

    registrar_gate_autenticacion(app)
    registrar_csrf_global(app)

    os.makedirs(app.config["DOCUMENTOS_DIR"], exist_ok=True)

    with app.app_context():
        aplicar_migraciones(directory=MIGRATIONS_DIR)
        if auto_seed:
            _bootstrap_datos_iniciales_si_vacio()

    @app.context_processor
    def inyectar_tema():
        return {"tema_actual": obtener_configuracion().tema}

    @app.get("/")
    def health():
        return redirect(url_for("vistas.dashboard"))

    @app.get("/api")
    def health_api():
        return jsonify({"status": "ok", "app": "gestion academica GREELEC"})

    return app


if __name__ == "__main__":
    host = os.environ.get("GREELEC_HOST", "127.0.0.1")
    port = int(os.environ.get("GREELEC_PORT", "5000"))
    debug = os.environ.get("GREELEC_DEBUG", "").strip().lower() in ("1", "true", "yes")
    app = create_app()
    app.run(host=host, port=port, debug=debug)
