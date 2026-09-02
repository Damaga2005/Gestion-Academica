import io
import os
import shutil
import sqlite3
import stat
import uuid
import zipfile
from datetime import datetime

from flask import Blueprint, current_app, request, jsonify, send_file

from models import db
from routes.errors import ApiError

backup_bp = Blueprint("backup", __name__)

# Tablas mínimas que debe tener cualquier backup reconocible de esta app, incluso uno
# generado por una versión antigua con un esquema todavía sin migrar del todo (las
# migraciones se aplican DESPUÉS de restaurar, así que aquí no se exige el esquema
# completo actual, solo que sea, sin duda, una base de datos de esta aplicación).
_TABLAS_OBLIGATORIAS = ("anio", "asignatura", "documento")

# Umbral a partir del cual se aplica la comprobación de ratio de compresión (una
# "zip bomb" real solo es peligrosa si el resultado descomprimido es grande).
_RATIO_CHECK_TAMANO_MINIMO = 1 * 1024 * 1024  # 1 MB


def _ruta_db_actual():
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    return uri.replace("sqlite:///", "", 1)


def _volcar_zip_backup(zf):
    """Añade la BD SQLite + toda la carpeta documentos/ al ZipFile ya abierto `zf`.
    Compartido entre construir_zip_backup() (en memoria, para la descarga por HTTP)
    y escribir_zip_backup() (directo a disco, para el backup automático — con
    documentos/ real pudiendo pesar más de 1 GB, duplicarlo en memoria de más no
    tiene sentido si de todas formas se va a escribir a un archivo)."""
    ruta_db = _ruta_db_actual()
    if os.path.isfile(ruta_db):
        zf.write(ruta_db, arcname="academico.db")

    documentos_dir = current_app.config["DOCUMENTOS_DIR"]
    for raiz, _dirs, archivos in os.walk(documentos_dir):
        for nombre in archivos:
            ruta_absoluta = os.path.join(raiz, nombre)
            ruta_relativa = os.path.join("documentos", os.path.relpath(ruta_absoluta, documentos_dir))
            zf.write(ruta_absoluta, arcname=ruta_relativa)


def construir_zip_backup():
    """BD SQLite + toda la carpeta documentos/ en un .zip en memoria (para send_file)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _volcar_zip_backup(zf)
    buffer.seek(0)
    return buffer


def escribir_zip_backup(destino):
    """Igual que construir_zip_backup() pero escribiendo directo a un archivo en
    disco, para el backup automático de escritorio.py."""
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        _volcar_zip_backup(zf)


@backup_bp.get("/backup/exportar")
def exportar_backup():
    """Genera un .zip con la BD SQLite + toda la carpeta documentos/, con fecha en el nombre."""
    nombre_zip = f"backup_{datetime.now().strftime('%Y-%m-%d')}.zip"
    buffer = construir_zip_backup()
    return send_file(buffer, mimetype="application/zip", as_attachment=True, download_name=nombre_zip)


def _validar_zip_seguro(zf, destino_realpath):
    """Valida cada entrada del .zip ANTES de extraer nada, para evitar:
    - ZIP Slip: rutas absolutas, con '..' o enlaces simbólicos que escriban fuera de destino.
    - ZIP Bomb: demasiadas entradas, entradas individuales enormes, o un ratio de
      compresión sospechoso que indique una bomba de descompresión."""
    cfg = current_app.config
    infolist = zf.infolist()
    if len(infolist) > cfg["BACKUP_MAX_MEMBER_COUNT"]:
        raise ApiError("El .zip contiene demasiadas entradas")

    total = 0
    for info in infolist:
        nombre = info.filename
        if os.path.isabs(nombre) or nombre.startswith(("/", "\\")) or ":" in nombre:
            raise ApiError("El .zip contiene una ruta no permitida")

        modo = info.external_attr >> 16
        if stat.S_ISLNK(modo):
            raise ApiError("El .zip contiene enlaces simbólicos, no permitido")

        destino_miembro = os.path.realpath(os.path.join(destino_realpath, nombre))
        if destino_miembro != destino_realpath and not destino_miembro.startswith(destino_realpath + os.sep):
            raise ApiError("El .zip contiene una ruta que escapa del destino (Zip Slip)")

        if info.file_size > cfg["BACKUP_MAX_MEMBER_BYTES"]:
            raise ApiError("El .zip contiene un archivo individual demasiado grande")

        total += info.file_size
        if total > cfg["BACKUP_MAX_TOTAL_BYTES"]:
            raise ApiError("El .zip supera el tamaño total permitido al descomprimir")

        if info.file_size > _RATIO_CHECK_TAMANO_MINIMO and info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > cfg["BACKUP_MAX_COMPRESSION_RATIO"]:
                raise ApiError("El .zip parece una \"zip bomb\" (ratio de compresión sospechoso)")


def _validar_sqlite(ruta):
    """Abre `ruta` en modo solo lectura y comprueba que es una base de datos SQLite
    íntegra y reconocible como un backup de esta aplicación."""
    if not os.path.isfile(ruta):
        raise ApiError("El backup no contiene un academico.db válido")

    try:
        conexion = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    except sqlite3.Error as err:
        raise ApiError(f"El backup no contiene una base de datos SQLite válida: {err}")

    try:
        try:
            resultado = conexion.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as err:
            raise ApiError(f"El backup no contiene una base de datos SQLite válida: {err}")
        if not resultado or resultado[0] != "ok":
            raise ApiError("La base de datos del backup no pasa la comprobación de integridad")

        tablas_presentes = {
            fila[0] for fila in conexion.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        faltantes = [t for t in _TABLAS_OBLIGATORIAS if t not in tablas_presentes]
        if faltantes:
            raise ApiError(f"El backup no parece de esta aplicación (faltan tablas: {', '.join(faltantes)})")
    finally:
        conexion.close()


@backup_bp.post("/backup/importar")
def importar_backup():
    """Restaura la BD + documentos/ desde un .zip generado previamente con /backup/exportar.

    Restauración atómica con reversión completa ante cualquier fallo:
    1. Validar el .zip (Zip Slip / Zip Bomb) antes de extraer nada.
    2. Extraer en un directorio de trabajo temporal EN EL MISMO VOLUMEN que los datos
       reales (junto a DATA_DIR), no en el temp por defecto del SO: en Windows un
       "rename" atómico solo lo es dentro del mismo volumen.
    3. Validar la base SQLite extraída (integridad + tablas mínimas).
    4. Copiar automáticamente el estado actual (BD + documentos/) a un snapshot,
       ANTES de tocar nada real.
    5. Sustituir BD + documentos/, aplicar migraciones y re-validar con
       PRAGMA integrity_check sobre el fichero ya definitivo.
    6. Si cualquier paso de 4-5 falla, revertir desde el snapshot: el snapshot no se
       borra hasta que TODO lo anterior ha tenido éxito.

    Tras una restauración con éxito no se sigue sirviendo con la conexión antigua:
    se libera el engine y se pide reiniciar la aplicación.
    """
    archivo = request.files.get("backup")
    if not archivo or not archivo.filename:
        raise ApiError("Debes seleccionar un archivo .zip de backup")
    if not archivo.filename.lower().endswith(".zip"):
        raise ApiError("El backup debe ser un archivo .zip")

    ruta_db = _ruta_db_actual()
    documentos_dir = current_app.config["DOCUMENTOS_DIR"]
    data_dir = os.path.dirname(ruta_db)

    trabajo_dir = os.path.join(data_dir, ".restore_tmp", uuid.uuid4().hex)
    extraido_dir = os.path.join(trabajo_dir, "extraido")
    snapshot_dir = os.path.join(trabajo_dir, "snapshot")
    os.makedirs(extraido_dir, exist_ok=True)
    os.makedirs(snapshot_dir, exist_ok=True)

    try:
        ruta_zip = os.path.join(trabajo_dir, "subido.zip")
        archivo.save(ruta_zip)

        try:
            with zipfile.ZipFile(ruta_zip) as zf:
                if "academico.db" not in zf.namelist():
                    raise ApiError("El .zip no contiene academico.db: no parece un backup válido")
                _validar_zip_seguro(zf, os.path.realpath(extraido_dir))
                zf.extractall(extraido_dir)
        except zipfile.BadZipFile:
            raise ApiError("El archivo no es un .zip válido")

        db_extraida = os.path.join(extraido_dir, "academico.db")
        _validar_sqlite(db_extraida)

        # Snapshot pre-restauración: se conserva hasta que TODO el resto tenga éxito.
        snapshot_db = os.path.join(snapshot_dir, "academico.db")
        if os.path.isfile(ruta_db):
            shutil.copyfile(ruta_db, snapshot_db)
        snapshot_documentos = os.path.join(snapshot_dir, "documentos")
        documentos_habia = os.path.isdir(documentos_dir)
        if documentos_habia:
            shutil.copytree(documentos_dir, snapshot_documentos)

        # Liberar las conexiones abiertas de SQLAlchemy antes de sobrescribir el fichero .db
        db.session.remove()
        db.engine.dispose()

        try:
            shutil.copyfile(db_extraida, ruta_db)

            documentos_extraidos = os.path.join(extraido_dir, "documentos")
            if os.path.isdir(documentos_extraidos):
                if os.path.isdir(documentos_dir):
                    shutil.rmtree(documentos_dir)
                shutil.move(documentos_extraidos, documentos_dir)

            from flask_migrate import upgrade as aplicar_migraciones
            from config import MIGRATIONS_DIR
            aplicar_migraciones(directory=MIGRATIONS_DIR)

            # Re-validar sobre el fichero ya definitivo y migrado.
            _validar_sqlite(ruta_db)
        except Exception as err:
            # Revertir TODO al estado anterior: ni la BD ni documentos/ deben quedar
            # a medias ante un fallo en la sustitución, la migración o la re-validación.
            db.session.remove()
            db.engine.dispose()
            if os.path.isfile(snapshot_db):
                shutil.copyfile(snapshot_db, ruta_db)
            if documentos_habia:
                if os.path.isdir(documentos_dir):
                    shutil.rmtree(documentos_dir)
                shutil.move(snapshot_documentos, documentos_dir)
            elif os.path.isdir(documentos_dir):
                shutil.rmtree(documentos_dir)
            raise ApiError(
                f"No se pudo completar la restauración; se ha revertido al estado anterior ({err})"
            ) from None
        finally:
            # No seguir sirviendo peticiones con conexiones apuntando al fichero anterior.
            db.session.remove()
            db.engine.dispose()
    finally:
        shutil.rmtree(trabajo_dir, ignore_errors=True)

    return jsonify({
        "status": "ok",
        "requiere_reinicio": True,
        "mensaje": "Backup restaurado correctamente. Reinicia la aplicación para que los cambios surtan efecto.",
    })
