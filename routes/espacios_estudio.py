from flask import Blueprint, request, jsonify

from models import db, EspacioEstudio, EspacioEstudioDocumento, ObjetivoEspacio, TareaEvento, Documento
from routes.errors import ApiError
from routes.busqueda import _normalizar, _contiene

espacios_estudio_bp = Blueprint("espacios_estudio", __name__)


@espacios_estudio_bp.get("/espacios-estudio")
def listar_espacios():
    espacios = (
        EspacioEstudio.query.join(TareaEvento)
        .order_by(TareaEvento.fecha)
        .all()
    )
    return jsonify([e.to_dict() for e in espacios])


@espacios_estudio_bp.post("/espacios-estudio")
def crear_espacio():
    data = request.get_json(silent=True) or {}
    if "tarea_evento_id" not in data:
        raise ApiError("'tarea_evento_id' es obligatorio")

    tarea = TareaEvento.query.get(data["tarea_evento_id"])
    if tarea is None:
        raise ApiError(f"no existe ninguna tarea/evento con id '{data['tarea_evento_id']}'", 404)

    # Idempotente (spec: el checkbox del calendario puede reenviarse al editar una
    # tarea que ya tiene espacio): si ya existe, se devuelve tal cual en vez de fallar.
    if tarea.espacio_estudio is not None:
        return jsonify(tarea.espacio_estudio.to_dict()), 200

    espacio = EspacioEstudio(
        tarea_evento_id=tarea.id,
        nombre=data.get("nombre") or tarea.titulo,
    )
    db.session.add(espacio)
    db.session.commit()
    return jsonify(espacio.to_dict()), 201


@espacios_estudio_bp.get("/espacios-estudio/<int:espacio_id>")
def obtener_espacio(espacio_id):
    espacio = EspacioEstudio.query.get_or_404(espacio_id)
    return jsonify(espacio.to_dict(include_detalle=True))


@espacios_estudio_bp.put("/espacios-estudio/<int:espacio_id>")
def actualizar_espacio(espacio_id):
    espacio = EspacioEstudio.query.get_or_404(espacio_id)
    data = request.get_json(silent=True) or {}
    if "nombre" in data:
        espacio.nombre = data["nombre"]
    db.session.commit()
    return jsonify(espacio.to_dict())


@espacios_estudio_bp.delete("/espacios-estudio/<int:espacio_id>")
def borrar_espacio(espacio_id):
    espacio = EspacioEstudio.query.get_or_404(espacio_id)
    db.session.delete(espacio)
    db.session.commit()
    return "", 204


@espacios_estudio_bp.get("/tareas/<int:tarea_id>/espacio-estudio")
def obtener_espacio_de_tarea(tarea_id):
    tarea = TareaEvento.query.get_or_404(tarea_id)
    if tarea.espacio_estudio is None:
        raise ApiError("esta tarea/evento no tiene Espacio de Estudio", 404)
    return jsonify(tarea.espacio_estudio.to_dict())


# --- Buscador de documentos para "+ Añadir documento" (nunca duplica: solo referencia) ---

@espacios_estudio_bp.get("/espacios-estudio/buscar-documentos")
def buscar_documentos_para_espacio():
    q = request.args.get("q", "").strip()
    asignatura_id = request.args.get("asignatura_id", type=int)
    categoria = request.args.get("categoria")
    etiqueta = request.args.get("etiqueta", "").strip()
    excluir_espacio_id = request.args.get("excluir_espacio_id", type=int)

    ya_referenciados = set()
    if excluir_espacio_id is not None:
        ya_referenciados = {
            ref.documento_id for ref in
            EspacioEstudioDocumento.query.filter_by(espacio_estudio_id=excluir_espacio_id).all()
        }

    query = Documento.query
    if asignatura_id is not None:
        query = query.filter_by(asignatura_id=asignatura_id)
    if categoria:
        query = query.filter_by(categoria=categoria)

    resultados = []
    for d in query.all():
        if d.id in ya_referenciados:
            continue
        if q and not _contiene(d.nombre_archivo, q):
            continue
        if etiqueta and etiqueta.lower() not in [e.lower() for e in d.lista_etiquetas()]:
            continue
        resultados.append({
            "id": d.id,
            "nombre_archivo": d.nombre_archivo,
            "asignatura_id": d.asignatura_id,
            "asignatura_nombre": d.asignatura.nombre if d.asignatura else None,
            "asignatura_siglas": d.asignatura.siglas if d.asignatura else None,
            "categoria": d.categoria,
            "etiquetas": d.lista_etiquetas(),
        })

    resultados.sort(key=lambda r: _normalizar(r["nombre_archivo"]))
    return jsonify(resultados[:100])


@espacios_estudio_bp.post("/espacios-estudio/<int:espacio_id>/documentos")
def anadir_documento_a_espacio(espacio_id):
    espacio = EspacioEstudio.query.get_or_404(espacio_id)
    data = request.get_json(silent=True) or {}
    for campo in ("documento_id", "seccion"):
        if campo not in data:
            raise ApiError(f"'{campo}' es obligatorio")

    documento = Documento.query.get(data["documento_id"])
    if documento is None:
        raise ApiError(f"no existe ningún documento con id '{data['documento_id']}'", 404)

    ya_existe = EspacioEstudioDocumento.query.filter_by(
        espacio_estudio_id=espacio.id, documento_id=documento.id
    ).first()
    if ya_existe is not None:
        raise ApiError("este documento ya está referenciado en el espacio", 409)

    max_orden = max((r.orden for r in espacio.documentos_ref), default=-1)
    ref = EspacioEstudioDocumento(
        espacio_estudio_id=espacio.id,
        documento_id=documento.id,
        seccion=data["seccion"],
        orden=max_orden + 1,
    )
    db.session.add(ref)
    db.session.commit()
    return jsonify(ref.to_dict()), 201


@espacios_estudio_bp.put("/espacios-estudio/documentos/<int:ref_id>")
def actualizar_documento_de_espacio(ref_id):
    ref = EspacioEstudioDocumento.query.get_or_404(ref_id)
    data = request.get_json(silent=True) or {}
    if "seccion" in data:
        ref.seccion = data["seccion"]
    if "leido" in data:
        ref.leido = bool(data["leido"])
    if "destacado" in data:
        ref.destacado = bool(data["destacado"])
    if "orden" in data:
        ref.orden = data["orden"]
    db.session.commit()
    return jsonify(ref.to_dict())


@espacios_estudio_bp.delete("/espacios-estudio/documentos/<int:ref_id>")
def quitar_documento_de_espacio(ref_id):
    ref = EspacioEstudioDocumento.query.get_or_404(ref_id)
    db.session.delete(ref)
    db.session.commit()
    return "", 204


# --- Checklist de objetivos ("✅ Tareas") ---

@espacios_estudio_bp.post("/espacios-estudio/<int:espacio_id>/objetivos")
def crear_objetivo(espacio_id):
    espacio = EspacioEstudio.query.get_or_404(espacio_id)
    data = request.get_json(silent=True) or {}
    if "texto" not in data:
        raise ApiError("'texto' es obligatorio")

    max_orden = max((o.orden for o in espacio.objetivos), default=-1)
    objetivo = ObjetivoEspacio(
        espacio_estudio_id=espacio.id,
        texto=data["texto"],
        orden=max_orden + 1,
    )
    db.session.add(objetivo)
    db.session.commit()
    return jsonify(objetivo.to_dict()), 201


@espacios_estudio_bp.put("/espacios-estudio/objetivos/<int:objetivo_id>")
def actualizar_objetivo(objetivo_id):
    objetivo = ObjetivoEspacio.query.get_or_404(objetivo_id)
    data = request.get_json(silent=True) or {}
    if "texto" in data:
        objetivo.texto = data["texto"]
    if "completada" in data:
        objetivo.completada = bool(data["completada"])
    db.session.commit()
    return jsonify(objetivo.to_dict())


@espacios_estudio_bp.delete("/espacios-estudio/objetivos/<int:objetivo_id>")
def borrar_objetivo(objetivo_id):
    objetivo = ObjetivoEspacio.query.get_or_404(objetivo_id)
    db.session.delete(objetivo)
    db.session.commit()
    return "", 204
