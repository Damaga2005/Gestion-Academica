import os
import shutil
from datetime import datetime

from flask import Blueprint, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename

from models import db, Documento, Apartado, PaginaTexto
from routes.errors import ApiError
from utils import carpeta_apartado, ruta_absoluta, nombre_archivo_disponible

documentos_bp = Blueprint("documentos", __name__)


def _indexar_texto_pdf(documento):
    """Extrae el texto de cada página del PDF con pypdf para poder buscar por contenido.
    Si el PDF no tiene texto extraíble (p. ej. escaneado como imagen) o está corrupto,
    simplemente no se indexa: no debe romper la subida del archivo."""
    try:
        from pypdf import PdfReader
        lector = PdfReader(ruta_absoluta(documento.ruta_local))
        for numero, pagina in enumerate(lector.pages, start=1):
            texto = (pagina.extract_text() or "").strip()
            if texto:
                db.session.add(PaginaTexto(documento_id=documento.id, numero_pagina=numero, contenido=texto))
    except Exception as err:
        current_app.logger.warning(f"No se pudo indexar el texto de '{documento.nombre_archivo}': {err}")


@documentos_bp.get("/apartados/<int:apartado_id>/documentos")
def listar_documentos(apartado_id):
    Apartado.query.get_or_404(apartado_id)
    documentos = Documento.query.filter_by(apartado_id=apartado_id).order_by(Documento.nombre_archivo).all()
    return jsonify([d.to_dict() for d in documentos])


@documentos_bp.post("/apartados/<int:apartado_id>/documentos")
def subir_documentos(apartado_id):
    """Subida múltiple: acepta uno o varios archivos en el campo 'archivos' (multipart/form-data)."""
    apartado = Apartado.query.get_or_404(apartado_id)
    asignatura = apartado.asignatura

    archivos = request.files.getlist("archivos")
    archivos = [a for a in archivos if a and a.filename]
    if not archivos:
        raise ApiError("no se ha enviado ningún archivo válido en el campo 'archivos'")

    carpeta = carpeta_apartado(asignatura, apartado)
    os.makedirs(carpeta, exist_ok=True)

    creados = []
    for archivo in archivos:
        nombre_seguro = secure_filename(archivo.filename)
        if not nombre_seguro:
            continue
        nombre_final = nombre_archivo_disponible(carpeta, nombre_seguro)
        ruta_disco = os.path.join(carpeta, nombre_final)
        archivo.save(ruta_disco)

        ruta_relativa = os.path.relpath(ruta_disco, current_app.config["DOCUMENTOS_DIR"]).replace(os.sep, "/")
        documento = Documento(
            asignatura_id=asignatura.id,
            apartado_id=apartado.id,
            nombre_archivo=nombre_final,
            ruta_local=ruta_relativa,
            fecha_subida=datetime.utcnow(),
        )
        db.session.add(documento)
        db.session.flush()  # necesitamos documento.id para indexar sus páginas
        if documento.es_pdf():
            _indexar_texto_pdf(documento)
        creados.append(documento)

    if not creados:
        raise ApiError("ningún archivo tenía un nombre válido para subir")

    db.session.commit()
    return jsonify([d.to_dict() for d in creados]), 201


@documentos_bp.get("/documentos/<int:documento_id>")
def obtener_documento(documento_id):
    documento = Documento.query.get_or_404(documento_id)
    return jsonify(documento.to_dict(include_marcadores=True))


@documentos_bp.get("/documentos/<int:documento_id>/archivo")
def servir_archivo(documento_id):
    documento = Documento.query.get_or_404(documento_id)
    carpeta, nombre = os.path.split(ruta_absoluta(documento.ruta_local))
    return send_from_directory(carpeta, nombre, as_attachment=False)


@documentos_bp.put("/documentos/<int:documento_id>")
def actualizar_documento(documento_id):
    documento = Documento.query.get_or_404(documento_id)
    data = request.get_json(silent=True) or {}
    if "nombre_archivo" in data:
        documento.nombre_archivo = data["nombre_archivo"]
    if "etiquetas" in data:
        valores = data["etiquetas"] or []
        documento.etiquetas = ", ".join(str(v).strip() for v in valores if str(v).strip()) or None
    db.session.commit()
    return jsonify(documento.to_dict())


@documentos_bp.get("/documentos/etiquetas")
def listar_etiquetas():
    """Todas las etiquetas ya usadas en algún documento, para poblar selectores de filtro."""
    etiquetas = set()
    for documento in Documento.query.filter(Documento.etiquetas.isnot(None)).all():
        etiquetas.update(documento.lista_etiquetas())
    return jsonify(sorted(etiquetas, key=str.lower))


@documentos_bp.post("/documentos/<int:documento_id>/ultima-pagina")
def actualizar_ultima_pagina(documento_id):
    documento = Documento.query.get_or_404(documento_id)
    data = request.get_json(silent=True) or {}
    if "pagina" not in data:
        raise ApiError("'pagina' es obligatorio")
    documento.ultima_pagina_vista = data["pagina"]
    db.session.commit()
    return jsonify(documento.to_dict())


@documentos_bp.delete("/documentos/<int:documento_id>")
def borrar_documento(documento_id):
    documento = Documento.query.get_or_404(documento_id)
    _borrar_archivo_fisico(documento)
    db.session.delete(documento)
    db.session.commit()
    return "", 204


def _borrar_archivo_fisico(documento):
    ruta = ruta_absoluta(documento.ruta_local)
    if os.path.exists(ruta):
        os.remove(ruta)


def _mover_documento_fisicamente(documento, apartado_destino):
    origen = ruta_absoluta(documento.ruta_local)
    carpeta_destino = carpeta_apartado(documento.asignatura, apartado_destino)
    os.makedirs(carpeta_destino, exist_ok=True)
    nombre_final = nombre_archivo_disponible(carpeta_destino, documento.nombre_archivo)
    destino = os.path.join(carpeta_destino, nombre_final)
    shutil.move(origen, destino)
    documento.nombre_archivo = nombre_final
    documento.ruta_local = os.path.relpath(destino, current_app.config["DOCUMENTOS_DIR"]).replace(os.sep, "/")
