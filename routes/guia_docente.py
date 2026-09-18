from flask import Blueprint, request, jsonify
from sqlalchemy import func

from models import db, Asignatura, Documento, Profesor, EsquemaEvaluacion, BloqueEvaluacion, ComponenteEvaluacion, TIPOS_COMPONENTE
from routes.errors import ApiError
from utils import ruta_absoluta
from guia_docente import analizar_guia_docente, extraer_texto

guia_docente_bp = Blueprint("guia_docente", __name__)


@guia_docente_bp.post("/documentos/<int:documento_id>/analizar-guia-docente")
def analizar_documento_guia_docente(documento_id):
    """Solo lectura: extrae y propone datos, NUNCA escribe nada en la base de
    datos. La escritura solo ocurre en /importar-guia-docente, con los datos que
    el usuario haya confirmado (y editado si ha hecho falta) en la pantalla de
    previsualización."""
    documento = Documento.query.get_or_404(documento_id)
    if not documento.es_pdf():
        raise ApiError("solo se puede analizar un documento PDF")

    try:
        texto = extraer_texto(ruta_absoluta(documento.ruta_local))
    except Exception as err:
        raise ApiError(f"no se ha podido leer el PDF: {err}")

    resultado = analizar_guia_docente(texto)
    asignatura = documento.asignatura

    return jsonify({
        "profesores": resultado["profesores"],
        "esquemas": resultado["esquemas"],
        "asignatura_tiene_profesores": len(asignatura.profesores) > 0,
        "asignatura_tiene_esquemas": len(asignatura.esquemas) > 0,
    })


def _validar_modo(valor, campo):
    if valor not in ("añadir", "reemplazar"):
        raise ApiError(f"'{campo}' debe ser 'añadir' o 'reemplazar'")
    return valor


@guia_docente_bp.post("/asignaturas/<int:asignatura_id>/importar-guia-docente")
def importar_guia_docente(asignatura_id):
    """Escribe en la BD exactamente los profesores/esquemas que vienen en el
    cuerpo de la petición (los que el usuario dejó en la pantalla de
    confirmación tras revisar/editar la propuesta), nunca los que devolvió el
    análisis automático directamente."""
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}

    profesores_datos = data.get("profesores", [])
    esquemas_datos = data.get("esquemas", [])

    if profesores_datos:
        modo_profesores = _validar_modo(data.get("modo_profesores", "añadir"), "modo_profesores")
        if modo_profesores == "reemplazar":
            Profesor.query.filter_by(asignatura_id=asignatura_id).delete()

        max_orden = db.session.query(func.max(Profesor.orden)).filter_by(
            asignatura_id=asignatura_id
        ).scalar() or 0
        for i, p in enumerate(profesores_datos):
            if not p.get("nombre"):
                raise ApiError("cada profesor necesita un nombre")
            db.session.add(Profesor(
                asignatura_id=asignatura_id,
                nombre=p["nombre"].strip(),
                rol=(p.get("rol") or "").strip() or None,
                correo=(p.get("correo") or "").strip() or None,
                despacho=(p.get("despacho") or "").strip() or None,
                aula_virtual=(p.get("aula_virtual") or "").strip() or None,
                orden=max_orden + 1 + i,
            ))

    if esquemas_datos:
        modo_esquemas = _validar_modo(data.get("modo_esquemas", "añadir"), "modo_esquemas")
        if modo_esquemas == "reemplazar":
            # Uno a uno (no bulk .delete()): dispara la cascade de cada esquema a sus
            # ComponenteEvaluacion (models.py). Un bulk delete la salta y deja
            # componentes huérfanos apuntando a un esquema_id ya borrado — ya pasó
            # una vez con datos reales de CCE.
            for esquema in EsquemaEvaluacion.query.filter_by(asignatura_id=asignatura_id).all():
                db.session.delete(esquema)

        max_orden = db.session.query(func.max(EsquemaEvaluacion.orden)).filter_by(
            asignatura_id=asignatura_id
        ).scalar() or 0
        for i, esquema_datos in enumerate(esquemas_datos):
            if not esquema_datos.get("nombre"):
                raise ApiError("cada esquema necesita un nombre")
            componentes = esquema_datos.get("componentes") or []
            bloques = esquema_datos.get("bloques") or []
            for b in bloques:
                if not b.get("nombre"):
                    raise ApiError("cada bloque necesita un nombre")
                if b.get("porcentaje") is None:
                    raise ApiError(f"el bloque '{b['nombre']}' necesita un porcentaje")
            for c in componentes + [sub for b in bloques for sub in (b.get("componentes") or [])]:
                if not c.get("nombre"):
                    raise ApiError("cada componente necesita un nombre")
                if c.get("tipo") not in TIPOS_COMPONENTE:
                    raise ApiError(f"tipo de componente debe ser uno de {TIPOS_COMPONENTE}")
                if c.get("porcentaje") is None:
                    raise ApiError(f"el componente '{c['nombre']}' necesita un porcentaje")

            esquema = EsquemaEvaluacion(
                asignatura_id=asignatura_id, nombre=esquema_datos["nombre"].strip(), orden=max_orden + 1 + i,
            )
            db.session.add(esquema)
            db.session.flush()
            for c in componentes:
                db.session.add(ComponenteEvaluacion(
                    asignatura_id=asignatura_id, esquema_id=esquema.id,
                    nombre=c["nombre"].strip(), tipo=c["tipo"], porcentaje=c["porcentaje"],
                ))
            for j, b in enumerate(bloques):
                bloque = BloqueEvaluacion(
                    esquema_id=esquema.id, nombre=b["nombre"].strip(), porcentaje=b["porcentaje"], orden=j,
                )
                db.session.add(bloque)
                db.session.flush()
                for c in b.get("componentes") or []:
                    db.session.add(ComponenteEvaluacion(
                        asignatura_id=asignatura_id, esquema_id=esquema.id, bloque_id=bloque.id,
                        nombre=c["nombre"].strip(), tipo=c["tipo"], porcentaje=c["porcentaje"],
                    ))

    db.session.commit()
    return jsonify(asignatura.to_dict())
