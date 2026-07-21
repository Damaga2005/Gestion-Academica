import socket

from flask import Blueprint, render_template, current_app

from models import Anio, Asignatura

vistas_bp = Blueprint("vistas", __name__)


def _detectar_ip_local():
    """IP de este equipo en la red local (para acceder desde el móvil, ver spec punto 10)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


@vistas_bp.get("/vista/dashboard")
def dashboard():
    from routes.notificaciones import calcular_notificaciones

    notificaciones = calcular_notificaciones()
    return render_template("dashboard.html", notificaciones=notificaciones)


@vistas_bp.get("/vista")
def index():
    anios = Anio.query.order_by(Anio.numero).all()
    return render_template("index.html", anios=anios)


@vistas_bp.get("/vista/asignaturas/<int:asignatura_id>")
def vista_asignatura(asignatura_id):
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    return render_template("asignatura.html", asignatura=asignatura)


@vistas_bp.get("/vista/calendario")
def vista_calendario():
    return render_template("calendario.html")


@vistas_bp.get("/vista/horario")
def vista_horario():
    return render_template("horario.html")


@vistas_bp.get("/vista/repaso")
def vista_repaso():
    return render_template("repaso.html")


@vistas_bp.get("/vista/ajustes")
def vista_ajustes():
    return render_template(
        "ajustes.html",
        ip_local=_detectar_ip_local(),
        documentos_dir=current_app.config["DOCUMENTOS_DIR"],
    )


@vistas_bp.get("/vista/changelog")
def vista_changelog():
    from changelog import CAMBIOS
    return render_template("changelog.html", cambios=CAMBIOS)
