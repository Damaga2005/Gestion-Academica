import os
import secrets
import sys

from dotenv import load_dotenv


def _resource_dir():
    """Carpeta de recursos de solo lectura (plantillas, estáticos, pdf.js, migraciones).
    Empaquetado con PyInstaller, viven dentro del bundle (sys._MEIPASS)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.abspath(os.path.dirname(__file__))


def _data_dir():
    """Carpeta de datos persistentes (BD SQLite, documentos/, .env).
    Empaquetado, debe vivir junto al .exe, no dentro del bundle temporal."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))


RESOURCE_DIR = _resource_dir()
DATA_DIR = _data_dir()
BASE_DIR = DATA_DIR  # compatibilidad con el resto del código, que asume "la carpeta del proyecto"
MIGRATIONS_DIR = os.path.join(RESOURCE_DIR, "migrations")

# Carga variables desde un .env junto a los datos (DATA_DIR), si existe. No falla si no hay archivo.
load_dotenv(os.path.join(DATA_DIR, ".env"))

# SECRET_KEY de sesión (independiente de GREELEC_LOCK_KEY, spec Fase 11 punto 3).
# Si no se define FLASK_SECRET_KEY, se genera una aleatoria en memoria: las sesiones
# dejan de ser válidas al reiniciar la app, pero esta nunca deja de arrancar por su ausencia.
_SECRET_KEY_POR_DEFECTO = secrets.token_hex(32)


class Config:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(DATA_DIR, 'academico.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    DOCUMENTOS_DIR = os.path.join(DATA_DIR, "documentos")
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB por petición (subida múltiple de PDFs)

    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or _SECRET_KEY_POR_DEFECTO
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # No se activa SESSION_COOKIE_SECURE: la app también se sirve por HTTP plano en la
    # red local (acceso desde el móvil, spec punto 10) y un navegador nunca envía
    # cookies "Secure" sobre HTTP sin cifrar, lo que rompería el login por sesión ahí.
