from flask import Blueprint, request, jsonify
from sqlalchemy.orm import joinedload

from models import (
    Asignatura, Documento, PaginaTexto, Profesor, TareaEvento,
    BusquedaFavorito, BusquedaReciente, db,
)
from routes.errors import ApiError
from utils import normalizar_busqueda

busqueda_bp = Blueprint("busqueda", __name__)

LIMITE_POR_GRUPO = 25
LIMITE_RECIENTES = 15
TIPOS_TAREA_EXAMEN = ("examen", "examen_parcial", "examen_final", "recuperacion")

_normalizar = normalizar_busqueda


def _contiene(texto, termino):
    return bool(texto) and _normalizar(termino) in _normalizar(texto)


def _pagina_coincide(pagina, termino):
    """Como _contiene(), pero reutiliza PaginaTexto.contenido_normalizado en vez de
    volver a normalizar el contenido completo del PDF en cada búsqueda (con miles de
    páginas indexadas, eso era el cuello de botella real de /buscar). Si una fila
    todavía no tiene el campo precalculado (datos de antes de esta migración), cae
    en normalizar al vuelo para no perder resultados."""
    normalizado = pagina.contenido_normalizado
    if normalizado is None:
        normalizado = _normalizar(pagina.contenido)
    return _normalizar(termino) in normalizado


def _fragmento(texto, termino, radio=60):
    idx = _normalizar(texto).find(_normalizar(termino))
    if idx == -1:
        return texto[:120]
    inicio = max(0, idx - radio)
    fin = min(len(texto), idx + len(termino) + radio)
    return f"{'…' if inicio > 0 else ''}{texto[inicio:fin]}{'…' if fin < len(texto) else ''}"


@busqueda_bp.get("/buscar")
def buscar():
    termino = (request.args.get("q") or "").strip()
    etiqueta = (request.args.get("etiqueta") or "").strip()

    if not termino and not etiqueta:
        raise ApiError("Indica un término de búsqueda ('q') y/o una etiqueta")

    resultados = {
        "asignaturas": [], "profesores": [], "documentos": [], "paginas_pdf": [],
        "notas": [], "tareas": [], "examenes": [], "eventos": [], "etiquetas": [],
    }

    if termino:
        for a in Asignatura.query.all():
            if _contiene(a.nombre, termino):
                resultados["asignaturas"].append({"id": a.id, "nombre": a.nombre, "url": f"/vista/asignaturas/{a.id}"})
            if _contiene(a.notas, termino):
                resultados["notas"].append({
                    "asignatura_id": a.id,
                    "asignatura_nombre": a.nombre,
                    "fragmento": _fragmento(a.notas, termino),
                    "url": f"/vista/asignaturas/{a.id}",
                })

        for p in Profesor.query.options(joinedload(Profesor.asignatura)).all():
            if _contiene(p.nombre, termino):
                resultados["profesores"].append({
                    "id": p.id,
                    "nombre": p.nombre,
                    "rol": p.rol,
                    "asignatura_id": p.asignatura_id,
                    "asignatura_nombre": p.asignatura.nombre if p.asignatura else None,
                    "url": f"/vista/asignaturas/{p.asignatura_id}",
                })

        for t in TareaEvento.query.all():
            if not _contiene(t.titulo, termino):
                continue
            item = {
                "id": t.id,
                "titulo": t.titulo,
                "fecha": t.fecha.isoformat(),
                "tipo": t.tipo,
                "url": f"/vista/calendario?anio={t.fecha.year}&mes={t.fecha.month}",
            }
            if t.tipo in TIPOS_TAREA_EXAMEN:
                resultados["examenes"].append(item)
            elif t.tipo == "evento":
                resultados["eventos"].append(item)
            else:
                resultados["tareas"].append(item)

        for p in PaginaTexto.query.options(joinedload(PaginaTexto.documento)).all():
            if _pagina_coincide(p, termino):
                doc = p.documento
                resultados["paginas_pdf"].append({
                    "documento_id": doc.id,
                    "nombre_archivo": doc.nombre_archivo,
                    "asignatura_id": doc.asignatura_id,
                    "numero_pagina": p.numero_pagina,
                    "fragmento": _fragmento(p.contenido, termino),
                    "url": f"/vista/asignaturas/{doc.asignatura_id}?doc={doc.id}&pagina={p.numero_pagina}",
                })

    # Una sola pasada por todos los documentos: sirve tanto para las coincidencias
    # por nombre/etiqueta (bloque de abajo) como para las etiquetas sugeridas (si
    # hay término), evitando cargar la tabla completa dos veces.
    todos_documentos = Documento.query.all()

    if termino:
        etiquetas_vistas = set()
        for d in todos_documentos:
            if not d.etiquetas:
                continue
            for et in d.lista_etiquetas():
                if et.lower() in etiquetas_vistas:
                    continue
                if _contiene(et, termino):
                    etiquetas_vistas.add(et.lower())
                    resultados["etiquetas"].append({"etiqueta": et, "url": f"/buscar?etiqueta={et}"})

    for d in todos_documentos:
        etiquetas_doc = [e.lower() for e in d.lista_etiquetas()]
        if etiqueta and etiqueta.lower() not in etiquetas_doc:
            continue
        if termino and not _contiene(d.nombre_archivo, termino):
            continue
        resultados["documentos"].append({
            "id": d.id,
            "nombre_archivo": d.nombre_archivo,
            "asignatura_id": d.asignatura_id,
            "etiquetas": d.lista_etiquetas(),
            "url": f"/vista/asignaturas/{d.asignatura_id}?doc={d.id}",
        })

    for clave in resultados:
        resultados[clave] = resultados[clave][:LIMITE_POR_GRUPO]

    return jsonify(resultados)


@busqueda_bp.get("/busqueda/favoritos")
def listar_favoritos():
    favoritos = BusquedaFavorito.query.order_by(BusquedaFavorito.fecha_creacion.desc()).all()
    return jsonify([f.to_dict() for f in favoritos])


@busqueda_bp.post("/busqueda/favoritos")
def anadir_favorito():
    data = request.get_json(silent=True) or {}
    tipo_entidad = data.get("tipo_entidad")
    entidad_id = data.get("entidad_id")
    if not tipo_entidad or entidad_id is None:
        raise ApiError("'tipo_entidad' y 'entidad_id' son obligatorios")

    existente = BusquedaFavorito.query.filter_by(tipo_entidad=tipo_entidad, entidad_id=entidad_id).first()
    if existente:
        return jsonify(existente.to_dict())

    favorito = BusquedaFavorito(tipo_entidad=tipo_entidad, entidad_id=entidad_id)
    db.session.add(favorito)
    db.session.commit()
    return jsonify(favorito.to_dict()), 201


@busqueda_bp.delete("/busqueda/favoritos")
def quitar_favorito():
    tipo_entidad = request.args.get("tipo_entidad")
    entidad_id = request.args.get("entidad_id", type=int)
    if not tipo_entidad or entidad_id is None:
        raise ApiError("'tipo_entidad' y 'entidad_id' son obligatorios")

    BusquedaFavorito.query.filter_by(tipo_entidad=tipo_entidad, entidad_id=entidad_id).delete()
    db.session.commit()
    return "", 204


@busqueda_bp.get("/busqueda/recientes")
def listar_recientes():
    recientes = (
        BusquedaReciente.query.order_by(BusquedaReciente.fecha_acceso.desc()).limit(LIMITE_RECIENTES).all()
    )
    return jsonify([r.to_dict() for r in recientes])


@busqueda_bp.post("/busqueda/recientes")
def registrar_reciente():
    data = request.get_json(silent=True) or {}
    tipo_entidad = data.get("tipo_entidad")
    entidad_id = data.get("entidad_id")
    etiqueta_mostrada = (data.get("etiqueta_mostrada") or "").strip()
    url = (data.get("url") or "").strip()
    if not tipo_entidad or entidad_id is None or not etiqueta_mostrada or not url:
        raise ApiError("'tipo_entidad', 'entidad_id', 'etiqueta_mostrada' y 'url' son obligatorios")

    # Evita duplicar la misma entrada: se borra la anterior y se reinserta al final (más reciente).
    BusquedaReciente.query.filter_by(tipo_entidad=tipo_entidad, entidad_id=entidad_id).delete()
    db.session.add(BusquedaReciente(
        tipo_entidad=tipo_entidad, entidad_id=entidad_id,
        etiqueta_mostrada=etiqueta_mostrada, url=url,
    ))
    db.session.commit()

    # Recorta al límite: solo conservamos las últimas LIMITE_RECIENTES entradas.
    sobrantes = (
        BusquedaReciente.query.order_by(BusquedaReciente.fecha_acceso.desc())
        .offset(LIMITE_RECIENTES).all()
    )
    for r in sobrantes:
        db.session.delete(r)
    db.session.commit()
    return "", 204
