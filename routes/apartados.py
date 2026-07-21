import os
import shutil

from flask import Blueprint, request, jsonify
from sqlalchemy import func

from models import db, Apartado, Asignatura
from routes.errors import ApiError
from routes.documentos import _borrar_archivo_fisico, _mover_documento_fisicamente
from utils import carpeta_apartado

apartados_bp = Blueprint("apartados", __name__)


@apartados_bp.get("/asignaturas/<int:asignatura_id>/apartados")
def listar_apartados(asignatura_id):
    Asignatura.query.get_or_404(asignatura_id)
    apartados = Apartado.query.filter_by(asignatura_id=asignatura_id).order_by(Apartado.orden).all()
    return jsonify([a.to_dict() for a in apartados])


@apartados_bp.post("/asignaturas/<int:asignatura_id>/apartados")
def crear_apartado(asignatura_id):
    """Añade un apartado propio adicional a los 3 de partida (Teoría/Exámenes/Laboratorio)."""
    Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}
    if "nombre" not in data:
        raise ApiError("'nombre' es obligatorio")

    max_orden = db.session.query(func.max(Apartado.orden)).filter_by(asignatura_id=asignatura_id).scalar() or 0
    apartado = Apartado(
        asignatura_id=asignatura_id,
        nombre=data["nombre"],
        orden=data.get("orden", max_orden + 1),
    )
    db.session.add(apartado)
    db.session.commit()
    return jsonify(apartado.to_dict()), 201


@apartados_bp.put("/apartados/<int:apartado_id>")
def actualizar_apartado(apartado_id):
    apartado = Apartado.query.get_or_404(apartado_id)
    data = request.get_json(silent=True) or {}
    if "nombre" in data:
        apartado.nombre = data["nombre"]
    if "orden" in data:
        apartado.orden = data["orden"]
    db.session.commit()
    return jsonify(apartado.to_dict())


@apartados_bp.delete("/apartados/<int:apartado_id>")
def borrar_apartado(apartado_id):
    """
    Elimina un apartado. Si tiene documentos, exige indicar qué hacer con ellos vía
    query param 'accion':
      - Sin 'accion' y con documentos -> 409, devuelve el listado para que el cliente decida.
      - accion=eliminar_documentos -> borra también los documentos (archivo físico + fila).
      - accion=mover&apartado_destino_id=<id> -> mueve los documentos a otro apartado antes de borrar.
    """
    apartado = Apartado.query.get_or_404(apartado_id)
    accion = request.args.get("accion")
    documentos = list(apartado.documentos)

    if documentos and accion is None:
        return jsonify({
            "error": "el apartado tiene documentos: decide qué hacer con ellos antes de borrarlo",
            "documentos": [d.to_dict() for d in documentos],
            "opciones": {
                "eliminar_documentos": "?accion=eliminar_documentos (borra también los archivos físicos)",
                "mover": "?accion=mover&apartado_destino_id=<id> (mueve los documentos a otro apartado antes de borrar)",
            },
        }), 409

    if documentos:
        if accion == "mover":
            destino_id = request.args.get("apartado_destino_id", type=int)
            if not destino_id:
                raise ApiError("'apartado_destino_id' es obligatorio con accion=mover")
            destino = Apartado.query.get_or_404(destino_id)
            if destino.id == apartado.id:
                raise ApiError("el apartado destino debe ser distinto del que se borra")
            if destino.asignatura_id != apartado.asignatura_id:
                raise ApiError("el apartado destino debe pertenecer a la misma asignatura")
            for documento in documentos:
                _mover_documento_fisicamente(documento, destino)
                # Reasignar vía la relación ORM (no solo la FK cruda): así SQLAlchemy
                # saca el documento de apartado.documentos antes del cascade delete-orphan
                # que se dispara al borrar el apartado origen más abajo.
                documento.apartado = destino
        elif accion == "eliminar_documentos":
            # Solo se borran los archivos físicos aquí; las filas de Documento (y sus
            # marcadores/páginas de texto) las elimina en cascada el delete del apartado
            # de más abajo. Borrarlas también a mano provocaría un doble DELETE que
            # SQLAlchemy avisa como filas ya inexistentes (SAWarning "0 were matched").
            for documento in documentos:
                _borrar_archivo_fisico(documento)
        else:
            raise ApiError("accion debe ser 'eliminar_documentos' o 'mover'")
        db.session.flush()

    carpeta = carpeta_apartado(apartado.asignatura, apartado)
    db.session.delete(apartado)
    db.session.commit()
    if os.path.isdir(carpeta):
        shutil.rmtree(carpeta, ignore_errors=True)
    return "", 204
