import io
import os
import shutil
import tempfile
import zipfile
from datetime import datetime

from flask import Blueprint, current_app, request, jsonify, send_file

from models import db
from routes.errors import ApiError

backup_bp = Blueprint("backup", __name__)


def _ruta_db_actual():
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    return uri.replace("sqlite:///", "", 1)


@backup_bp.get("/backup/exportar")
def exportar_backup():
    """Genera un .zip con la BD SQLite + toda la carpeta documentos/, con fecha en el nombre."""
    nombre_zip = f"backup_{datetime.now().strftime('%Y-%m-%d')}.zip"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        ruta_db = _ruta_db_actual()
        if os.path.isfile(ruta_db):
            zf.write(ruta_db, arcname="academico.db")

        documentos_dir = current_app.config["DOCUMENTOS_DIR"]
        for raiz, _dirs, archivos in os.walk(documentos_dir):
            for nombre in archivos:
                ruta_absoluta = os.path.join(raiz, nombre)
                ruta_relativa = os.path.join("documentos", os.path.relpath(ruta_absoluta, documentos_dir))
                zf.write(ruta_absoluta, arcname=ruta_relativa)

    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True, download_name=nombre_zip)


@backup_bp.post("/backup/importar")
def importar_backup():
    """Restaura la BD + documentos/ desde un .zip generado previamente con /backup/exportar."""
    archivo = request.files.get("backup")
    if not archivo or not archivo.filename:
        raise ApiError("Debes seleccionar un archivo .zip de backup")
    if not archivo.filename.lower().endswith(".zip"):
        raise ApiError("El backup debe ser un archivo .zip")

    with tempfile.TemporaryDirectory() as tmp:
        ruta_zip = os.path.join(tmp, "subido.zip")
        archivo.save(ruta_zip)

        try:
            with zipfile.ZipFile(ruta_zip) as zf:
                if "academico.db" not in zf.namelist():
                    raise ApiError("El .zip no contiene academico.db: no parece un backup válido")
                zf.extractall(tmp)
        except zipfile.BadZipFile:
            raise ApiError("El archivo no es un .zip válido")

        # Liberar las conexiones abiertas de SQLAlchemy antes de sobrescribir el fichero .db
        db.session.remove()
        db.engine.dispose()

        shutil.copyfile(os.path.join(tmp, "academico.db"), _ruta_db_actual())

        documentos_dir = current_app.config["DOCUMENTOS_DIR"]
        documentos_extraidos = os.path.join(tmp, "documentos")
        if os.path.isdir(documentos_extraidos):
            if os.path.isdir(documentos_dir):
                shutil.rmtree(documentos_dir)
            shutil.move(documentos_extraidos, documentos_dir)

    return jsonify({
        "status": "ok",
        "mensaje": "Backup restaurado. Si algún dato no se refleja de inmediato, reinicia la app.",
    })
