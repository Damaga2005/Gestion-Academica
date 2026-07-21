import os
import re
import shutil
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func

from models import db, Asignatura, GrupoDocumento, Documento, CATEGORIAS_DOCUMENTO, ETIQUETA_CATEGORIA_DOCUMENTO
from routes.errors import ApiError
from routes.documentos import _indexar_texto_pdf
from utils import (
    carpeta_categoria, carpeta_grupo, ruta_absoluta, nombre_archivo_disponible,
    validar_archivo_subido, validar_cantidad_archivos,
)

grupos_documento_bp = Blueprint("grupos_documento", __name__)


def _validar_categoria(categoria):
    if categoria not in CATEGORIAS_DOCUMENTO:
        raise ApiError(f"categoria debe ser una de {CATEGORIAS_DOCUMENTO}", 404)
    return categoria


def _normalizar_nombre_grupo(nombre):
    limpio = re.sub(r"\s+", " ", (nombre or "")).strip()
    if not limpio:
        raise ApiError("'nombre' no puede estar vacío")
    return limpio


def _mover_archivo_fisico(documento, carpeta_destino):
    """Mueve el archivo en disco a `carpeta_destino` y actualiza nombre_archivo/ruta_local.
    Si el archivo ya no está en disco (no debería pasar) no bloquea la operación en BD:
    es mejor dejar la clasificación consistente que fallar toda la operación por eso."""
    origen = ruta_absoluta(documento.ruta_local)
    os.makedirs(carpeta_destino, exist_ok=True)
    if not os.path.exists(origen):
        return
    nombre_final = nombre_archivo_disponible(carpeta_destino, documento.nombre_archivo)
    destino = os.path.join(carpeta_destino, nombre_final)
    shutil.move(origen, destino)
    documento.nombre_archivo = nombre_final
    documento.ruta_local = os.path.relpath(destino, current_app.config["DOCUMENTOS_DIR"]).replace(os.sep, "/")


# --- Árbol completo (categorías + subgrupos + recuentos) ---

@grupos_documento_bp.get("/asignaturas/<int:asignatura_id>/documentos/arbol")
def arbol_documentos(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    resultado = []
    for categoria in CATEGORIAS_DOCUMENTO:
        grupos = GrupoDocumento.query.filter_by(
            asignatura_id=asignatura_id, categoria=categoria
        ).order_by(GrupoDocumento.orden, GrupoDocumento.nombre).all()
        sin_clasificar = Documento.query.filter_by(
            asignatura_id=asignatura_id, categoria=categoria, grupo_documento_id=None
        ).count()
        total = Documento.query.filter_by(asignatura_id=asignatura_id, categoria=categoria).count()
        resultado.append({
            "categoria": categoria,
            "etiqueta": ETIQUETA_CATEGORIA_DOCUMENTO[categoria],
            "grupos": [g.to_dict() for g in grupos],
            "sin_clasificar": sin_clasificar,
            "total_documentos": total,
        })
    return jsonify(resultado)


# --- Subgrupos ---

@grupos_documento_bp.get("/asignaturas/<int:asignatura_id>/grupos")
def listar_grupos(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    query = GrupoDocumento.query.filter_by(asignatura_id=asignatura_id)
    categoria = request.args.get("categoria")
    if categoria:
        _validar_categoria(categoria)
        query = query.filter_by(categoria=categoria)
    grupos = query.order_by(GrupoDocumento.categoria, GrupoDocumento.orden, GrupoDocumento.nombre).all()
    return jsonify([g.to_dict() for g in grupos])


@grupos_documento_bp.post("/asignaturas/<int:asignatura_id>/grupos")
def crear_grupo(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}
    if "categoria" not in data:
        raise ApiError("'categoria' es obligatoria")
    if "nombre" not in data:
        raise ApiError("'nombre' es obligatorio")

    categoria = _validar_categoria(data["categoria"])
    nombre = _normalizar_nombre_grupo(data["nombre"])

    existente = GrupoDocumento.query.filter_by(
        asignatura_id=asignatura_id, categoria=categoria, nombre=nombre
    ).first()
    if existente:
        raise ApiError(f"ya existe un subgrupo '{nombre}' en esta categoría", 409)

    max_orden = db.session.query(func.max(GrupoDocumento.orden)).filter_by(
        asignatura_id=asignatura_id, categoria=categoria
    ).scalar() or 0
    grupo = GrupoDocumento(
        asignatura_id=asignatura_id, categoria=categoria, nombre=nombre,
        orden=data.get("orden", max_orden + 1),
    )
    db.session.add(grupo)
    db.session.commit()
    return jsonify(grupo.to_dict()), 201


@grupos_documento_bp.put("/grupos/<int:grupo_id>")
def actualizar_grupo(grupo_id):
    """Renombrar y/o reordenar. El nombre se revalida contra duplicados dentro de la
    misma (asignatura, categoria) igual que al crear."""
    grupo = GrupoDocumento.query.get_or_404(grupo_id)
    data = request.get_json(silent=True) or {}

    if "nombre" in data:
        nombre = _normalizar_nombre_grupo(data["nombre"])
        existente = GrupoDocumento.query.filter_by(
            asignatura_id=grupo.asignatura_id, categoria=grupo.categoria, nombre=nombre
        ).filter(GrupoDocumento.id != grupo.id).first()
        if existente:
            raise ApiError(f"ya existe un subgrupo '{nombre}' en esta categoría", 409)
        grupo.nombre = nombre
    if "orden" in data:
        grupo.orden = data["orden"]

    db.session.commit()
    return jsonify(grupo.to_dict())


@grupos_documento_bp.delete("/grupos/<int:grupo_id>")
def borrar_grupo(grupo_id):
    """Elimina el subgrupo SIN borrar sus documentos (spec punto 5): los archivos
    físicos se mueven a la raíz de la categoría (que es donde vive "Sin clasificar")
    y su fila se desengancha del grupo, en vez de perderse."""
    grupo = GrupoDocumento.query.get_or_404(grupo_id)
    asignatura = grupo.asignatura
    destino = carpeta_categoria(asignatura, grupo.categoria)

    for documento in list(grupo.documentos):
        _mover_archivo_fisico(documento, destino)
        documento.grupo_documento_id = None
    db.session.flush()

    carpeta_origen = carpeta_grupo(asignatura, grupo)
    db.session.delete(grupo)
    db.session.commit()
    if os.path.isdir(carpeta_origen):
        shutil.rmtree(carpeta_origen, ignore_errors=True)
    return "", 204


# --- Documentos dentro de una categoría/subgrupo ---

@grupos_documento_bp.get("/asignaturas/<int:asignatura_id>/categorias/<categoria>/documentos")
def listar_documentos_categoria(asignatura_id, categoria):
    Asignatura.query.get_or_404(asignatura_id)
    _validar_categoria(categoria)

    query = Documento.query.filter_by(asignatura_id=asignatura_id, categoria=categoria)
    grupo_id = request.args.get("grupo_id", type=int)
    if grupo_id is not None:
        GrupoDocumento.query.get_or_404(grupo_id)
        query = query.filter_by(grupo_documento_id=grupo_id)
    elif request.args.get("todos") != "1":
        query = query.filter_by(grupo_documento_id=None)  # "Sin clasificar" por defecto

    documentos = query.order_by(Documento.nombre_archivo).all()
    return jsonify([d.to_dict() for d in documentos])


@grupos_documento_bp.post("/asignaturas/<int:asignatura_id>/categorias/<categoria>/documentos")
def subir_documentos_categoria(asignatura_id, categoria):
    """Subida múltiple (spec punto 6): 'archivos' en multipart/form-data, 'grupo_id'
    opcional en el mismo form. Sin grupo_id, el documento queda "Sin clasificar"
    dentro de la categoría (comportamiento al soltar sobre la categoría misma)."""
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    _validar_categoria(categoria)

    grupo = None
    grupo_id = request.form.get("grupo_id", type=int)
    if grupo_id:
        grupo = GrupoDocumento.query.get_or_404(grupo_id)
        if grupo.asignatura_id != asignatura_id or grupo.categoria != categoria:
            raise ApiError("el subgrupo indicado no pertenece a esta asignatura/categoría")

    archivos = request.files.getlist("archivos")
    archivos = [a for a in archivos if a and a.filename]
    if not archivos:
        raise ApiError("no se ha enviado ningún archivo válido en el campo 'archivos'")
    validar_cantidad_archivos(archivos)

    carpeta = carpeta_grupo(asignatura, grupo) if grupo else carpeta_categoria(asignatura, categoria)
    os.makedirs(carpeta, exist_ok=True)

    creados = []
    rutas_escritas = []
    try:
        for archivo in archivos:
            nombre_original = os.path.basename(archivo.filename or "")[:255]
            nombre_seguro = validar_archivo_subido(archivo)
            nombre_final = nombre_archivo_disponible(carpeta, nombre_seguro)
            ruta_disco = os.path.join(carpeta, nombre_final)
            archivo.save(ruta_disco)
            rutas_escritas.append(ruta_disco)

            ruta_relativa = os.path.relpath(ruta_disco, current_app.config["DOCUMENTOS_DIR"]).replace(os.sep, "/")
            documento = Documento(
                asignatura_id=asignatura.id,
                categoria=categoria,
                grupo_documento_id=grupo.id if grupo else None,
                nombre_archivo=nombre_final,
                nombre_original=nombre_original,
                ruta_local=ruta_relativa,
                tamano_bytes=os.path.getsize(ruta_disco),
                fecha_subida=datetime.utcnow(),
            )
            db.session.add(documento)
            db.session.flush()
            if documento.es_pdf():
                _indexar_texto_pdf(documento)
            creados.append(documento)
    except Exception:
        db.session.rollback()
        for ruta in rutas_escritas:
            if os.path.exists(ruta):
                os.remove(ruta)
        raise

    if not creados:
        raise ApiError("ningún archivo tenía un nombre válido para subir")

    db.session.commit()
    return jsonify([d.to_dict() for d in creados]), 201


@grupos_documento_bp.put("/documentos/<int:documento_id>/mover")
def mover_documento(documento_id):
    """Mueve un documento a otra categoría y/o subgrupo (spec punto 7: entre
    subgrupos, entre categorías, y destino del "Mover a..." / drag&drop interno).
    grupo_id ausente o null => "Sin clasificar" en la categoría destino."""
    documento = Documento.query.get_or_404(documento_id)
    data = request.get_json(silent=True) or {}
    if "categoria" not in data:
        raise ApiError("'categoria' es obligatoria")
    categoria = _validar_categoria(data["categoria"])

    grupo = None
    grupo_id = data.get("grupo_id")
    if grupo_id:
        grupo = GrupoDocumento.query.get_or_404(grupo_id)
        if grupo.asignatura_id != documento.asignatura_id or grupo.categoria != categoria:
            raise ApiError("el subgrupo indicado no pertenece a esta asignatura/categoría")

    asignatura = documento.asignatura
    destino = carpeta_grupo(asignatura, grupo) if grupo else carpeta_categoria(asignatura, categoria)
    _mover_archivo_fisico(documento, destino)
    documento.categoria = categoria
    documento.grupo_documento_id = grupo.id if grupo else None
    db.session.commit()
    return jsonify(documento.to_dict())
