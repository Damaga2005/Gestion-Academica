import os
import shutil
from datetime import datetime

from flask import Blueprint, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename

from models import db, Documento, Apartado, Asignatura, PaginaTexto, TareaEvento, registrar_actividad_hoy
from routes.errors import ApiError
from utils import (
    carpeta_apartado, ruta_absoluta, nombre_archivo_disponible,
    validar_archivo_subido, validar_cantidad_archivos, normalizar_busqueda,
)

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
                db.session.add(PaginaTexto(
                    documento_id=documento.id, numero_pagina=numero, contenido=texto,
                    contenido_normalizado=normalizar_busqueda(texto),
                ))
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
    validar_cantidad_archivos(archivos)

    carpeta = carpeta_apartado(asignatura, apartado)
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
                apartado_id=apartado.id,
                nombre_archivo=nombre_final,
                nombre_original=nombre_original,
                ruta_local=ruta_relativa,
                tamano_bytes=os.path.getsize(ruta_disco),
                fecha_subida=datetime.utcnow(),
            )
            db.session.add(documento)
            db.session.flush()  # necesitamos documento.id para indexar sus páginas
            if documento.es_pdf():
                _indexar_texto_pdf(documento)
            creados.append(documento)
    except Exception:
        # Subida transaccional: si algo falla a mitad de un lote, no deben quedar
        # archivos huérfanos en disco sin su fila correspondiente en la BD.
        db.session.rollback()
        for ruta in rutas_escritas:
            if os.path.exists(ruta):
                os.remove(ruta)
        raise

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
    respuesta = send_from_directory(carpeta, nombre, as_attachment=False)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    return respuesta


@documentos_bp.put("/documentos/<int:documento_id>")
def actualizar_documento(documento_id):
    documento = Documento.query.get_or_404(documento_id)
    data = request.get_json(silent=True) or {}
    if "nombre_archivo" in data:
        _renombrar_documento(documento, data["nombre_archivo"])
    if "etiquetas" in data:
        valores = data["etiquetas"] or []
        documento.etiquetas = ", ".join(str(v).strip() for v in valores if str(v).strip()) or None
    db.session.commit()
    return jsonify(documento.to_dict())


def _renombrar_documento(documento, nombre_propuesto):
    """Sanea el nombre nuevo con secure_filename (nunca se usa en crudo como
    componente de ruta), exige que conserve la extensión del archivo real (para no
    desincronizar es_pdf()/es_imagen() del contenido real ni colar una extensión no
    permitida) y renombra también el archivo físico en disco, no solo el metadato."""
    nombre_saneado = secure_filename(os.path.basename(nombre_propuesto or ""))
    if not nombre_saneado:
        raise ApiError("nombre de archivo no válido")

    extension_actual = documento.nombre_archivo.rsplit(".", 1)[-1].lower() if "." in documento.nombre_archivo else ""
    extension_nueva = nombre_saneado.rsplit(".", 1)[-1].lower() if "." in nombre_saneado else ""
    if extension_nueva != extension_actual:
        raise ApiError("no se puede cambiar la extensión del archivo al renombrarlo")

    if nombre_saneado == documento.nombre_archivo:
        return

    origen = ruta_absoluta(documento.ruta_local)
    carpeta = os.path.dirname(origen)
    nombre_final = nombre_archivo_disponible(carpeta, nombre_saneado)
    destino = os.path.join(carpeta, nombre_final)
    if os.path.exists(origen):
        shutil.move(origen, destino)
    documento.nombre_archivo = nombre_final
    documento.ruta_local = os.path.relpath(destino, current_app.config["DOCUMENTOS_DIR"]).replace(os.sep, "/")


@documentos_bp.get("/documentos/etiquetas")
def listar_etiquetas():
    """Todas las etiquetas ya usadas en algún documento, para poblar selectores de filtro."""
    etiquetas = set()
    for documento in Documento.query.filter(Documento.etiquetas.isnot(None)).all():
        etiquetas.update(documento.lista_etiquetas())
    return jsonify(sorted(etiquetas, key=str.lower))


@documentos_bp.get("/asignaturas/<int:asignatura_id>/documentos")
def listar_documentos_asignatura(asignatura_id):
    """Lista plana (sin agrupar por categoría/subgrupo) de los documentos de una
    asignatura, para el selector "Documento (opcional)" del formulario de tareas/
    exámenes (spec V2.2_VISOR_PDF, "integración con asignaturas y exámenes")."""
    Asignatura.query.get_or_404(asignatura_id)
    documentos = (
        Documento.query.filter_by(asignatura_id=asignatura_id)
        .order_by(Documento.nombre_archivo)
        .all()
    )
    if request.args.get("solo_pdf") == "1":
        documentos = [d for d in documentos if d.es_pdf()]
    return jsonify([d.to_dict() for d in documentos])


@documentos_bp.get("/documentos/recientes")
def documentos_recientes():
    """Documentos con progreso de lectura guardado, para la tarjeta "Continúa donde lo
    dejaste" del Dashboard (spec Continua_donde_lo_dejaste, punto 3)."""
    limite = request.args.get("limite", default=5, type=int)
    limite = max(1, min(limite, 100))
    documentos = (
        Documento.query.filter(Documento.fecha_ultima_apertura.isnot(None))
        .order_by(Documento.fecha_ultima_apertura.desc())
        .limit(limite)
        .all()
    )
    return jsonify([d.to_dict() for d in documentos])


@documentos_bp.post("/documentos/<int:documento_id>/progreso")
def actualizar_progreso(documento_id):
    """Guardado automático del estado de lectura (spec Continua_donde_lo_dejaste): página,
    porcentaje, zoom, modo de visualización, scroll y tiempo de lectura acumulado."""
    documento = Documento.query.get_or_404(documento_id)
    data = request.get_json(silent=True) or {}
    if "pagina" not in data:
        raise ApiError("'pagina' es obligatorio")

    ahora = datetime.utcnow()
    documento.ultima_pagina_vista = data["pagina"]
    if "porcentaje" in data:
        documento.porcentaje_leido = data["porcentaje"]
    if "zoom" in data:
        documento.zoom_nivel = data["zoom"]
    if "modo_visualizacion" in data:
        documento.modo_visualizacion = data["modo_visualizacion"]
    if "scroll" in data:
        documento.scroll_vertical = data["scroll"]
    if data.get("tiempo_sesion_segundos"):
        documento.tiempo_total_lectura_segundos += max(0, int(data["tiempo_sesion_segundos"]))
    if data.get("nueva_sesion"):
        documento.numero_sesiones += 1
        if documento.fecha_primera_apertura is None:
            documento.fecha_primera_apertura = ahora
    documento.fecha_ultima_apertura = ahora
    registrar_actividad_hoy()

    db.session.commit()
    return jsonify(documento.to_dict())


@documentos_bp.post("/documentos/<int:documento_id>/quitar-continuar")
def quitar_de_continuar(documento_id):
    """Desfija un documento de "Continúa donde lo dejaste" (Dashboard) sin perder su
    progreso de lectura: solo borra fecha_ultima_apertura (lo que usa /documentos/
    recientes para decidir qué mostrar), así que si se reabre el PDF sigue
    retomando por la misma página/zoom/scroll de antes."""
    documento = Documento.query.get_or_404(documento_id)
    documento.fecha_ultima_apertura = None
    db.session.commit()
    return "", 204


@documentos_bp.delete("/documentos/<int:documento_id>")
def borrar_documento(documento_id):
    documento = Documento.query.get_or_404(documento_id)
    _borrar_archivo_fisico(documento)
    # Desvincula (no borra) cualquier examen/tarea que enlazara este documento
    # (spec V2.2_VISOR_PDF): las referencias en Espacios de Estudio se limpian solas
    # vía cascade en el modelo.
    TareaEvento.query.filter_by(documento_id=documento.id).update({"documento_id": None})
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
