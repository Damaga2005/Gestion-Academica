from datetime import datetime

from flask import Blueprint, request, jsonify

from models import db, Asignatura, Cuatrimestre, TareaEvento, HorarioClase, ESTADOS_ASIGNATURA, resolver_asignatura, calcular_estado_notas
from routes.errors import ApiError
from utils import crear_apartados_por_defecto, borrar_carpeta_asignatura

asignaturas_bp = Blueprint("asignaturas", __name__)


def _verificar_siglas_disponibles(siglas, excluir_id=None):
    """Comprueba unicidad ANTES de tocar la sesión, para devolver un 409 claro en vez
    de dejar que el IntegrityError de SQLite reviente como un 500 sin manejar."""
    if not siglas:
        return
    normalizadas = siglas.strip().upper()
    if not normalizadas:
        return
    query = Asignatura.query.filter_by(siglas=normalizadas)
    if excluir_id is not None:
        query = query.filter(Asignatura.id != excluir_id)
    existente = query.first()
    if existente:
        raise ApiError(f"ya existe una asignatura con las siglas '{normalizadas}' (id={existente.id})", 409)


def cambiar_estado_asignatura(asignatura, nuevo_estado, commit=True):
    """
    Lógica de negocio centralizada para cambiar el estado de una asignatura (Fase 11).
    Separada de la función de ruta para poder reutilizarla: la usan tanto
    PATCH /api/asignaturas/<id>/estado como PUT /asignaturas/<id> y las rutas de
    elegir/quitar-elección de optativas, así el conjunto de estados válidos y su
    validación viven en un único sitio.

    Idempotente: fijar el mismo estado que ya tenía no produce ningún efecto distinto
    a fijar uno nuevo (solo se reasigna la columna y se guarda).
    """
    if nuevo_estado not in ESTADOS_ASIGNATURA:
        raise ApiError(f"estado debe ser uno de {ESTADOS_ASIGNATURA}", 422)

    # Nota: la lógica actual no exige nota_final para marcar 'superada' (el seed real
    # incluye asignaturas ya superadas sin nota histórica registrada), así que no se
    # añade aquí esa restricción: hacerlo inventaría una regla nueva no existente hasta
    # ahora y rompería datos reales ya guardados.
    asignatura.estado = nuevo_estado
    if commit:
        db.session.commit()
    return asignatura


def _set_prerrequisitos(asignatura, ids):
    if ids is None:
        return
    if ids:
        prerrequisitos = Asignatura.query.filter(Asignatura.id.in_(ids)).all()
        encontrados = {p.id for p in prerrequisitos}
        faltantes = set(ids) - encontrados
        if faltantes:
            raise ApiError(f"prerrequisitos_ids no encontrados: {sorted(faltantes)}")
        if asignatura.id in encontrados:
            raise ApiError("una asignatura no puede ser prerrequisito de sí misma")
        asignatura.prerrequisitos = prerrequisitos
    else:
        asignatura.prerrequisitos = []


# --- CRUD genérico de Asignatura ---

@asignaturas_bp.get("/asignaturas")
def listar_asignaturas():
    query = Asignatura.query
    cuatrimestre_id = request.args.get("cuatrimestre_id", type=int)
    tipo = request.args.get("tipo")
    estado = request.args.get("estado")
    if cuatrimestre_id is not None:
        query = query.filter_by(cuatrimestre_id=cuatrimestre_id)
    if tipo is not None:
        query = query.filter_by(tipo=tipo)
    if estado is not None:
        query = query.filter_by(estado=estado)
    asignaturas = query.order_by(Asignatura.nombre).all()
    return jsonify([a.to_dict(include_componentes=False) for a in asignaturas])


@asignaturas_bp.get("/asignaturas/media-curso")
def media_curso():
    """
    Agregado para la tarjeta "Media del Curso" (Dashboard): media general y
    estadísticas de aprobadas/suspendidas/pendientes a partir del indicador
    calcular_estado_notas (independiente del campo `estado` manual). Se
    excluyen las 'no_elegida' (catálogo de optativas sin elegir todavía, no
    son asignaturas "en curso" del usuario).
    """
    asignaturas = Asignatura.query.filter(Asignatura.estado != "no_elegida").all()
    estados = [calcular_estado_notas(a) for a in asignaturas]

    aprobadas = sum(1 for e in estados if e["estado_notas"] == "aprobada")
    suspendidas = sum(1 for e in estados if e["estado_notas"] == "suspendida")
    pendientes_evaluar = sum(1 for e in estados if e["estado_notas"] in ("en_progreso", "sin_evaluar"))
    notas = [e["nota_actual"] for e in estados if e["nota_actual"] is not None]

    return jsonify({
        "total": len(asignaturas),
        "aprobadas": aprobadas,
        "suspendidas": suspendidas,
        "pendientes_evaluar": pendientes_evaluar,
        "nota_mas_alta": max(notas) if notas else None,
        "nota_mas_baja": min(notas) if notas else None,
        "media_general": round(sum(notas) / len(notas), 2) if notas else None,
    })


@asignaturas_bp.get("/asignaturas/<string:identificador>")
def obtener_asignatura(identificador):
    """
    Acepta tanto el id numérico como las siglas oficiales (spec Fase Calendario/
    Horario punto 1): /asignaturas/16 y /asignaturas/DSED resuelven la misma
    asignatura. Las relaciones internas siguen usando el id numérico en todo
    momento; esto es solo la puerta de entrada pública.
    """
    asignatura = resolver_asignatura(identificador)
    if asignatura is None:
        raise ApiError("recurso no encontrado", 404)
    return jsonify(asignatura.to_dict(include_componentes=True))


@asignaturas_bp.post("/asignaturas")
def crear_asignatura():
    data = request.get_json(silent=True) or {}
    for campo in ("cuatrimestre_id", "nombre", "creditos_ects"):
        if campo not in data:
            raise ApiError(f"'{campo}' es obligatorio")

    Cuatrimestre.query.get_or_404(data["cuatrimestre_id"])
    _verificar_siglas_disponibles(data.get("siglas"))

    asignatura = Asignatura(
        cuatrimestre_id=data["cuatrimestre_id"],
        nombre=data["nombre"],
        siglas=data.get("siglas"),
        creditos_ects=data["creditos_ects"],
        tipo=data.get("tipo", "obligatoria"),
        estado=data.get("estado", "pendiente"),
        nota_final=data.get("nota_final"),
        origen_catalogo=data.get("origen_catalogo", False),
        nombre_profesor=data.get("nombre_profesor"),
        despacho_profesor=data.get("despacho_profesor"),
        correo_profesor=data.get("correo_profesor"),
        link_aula_virtual=data.get("link_aula_virtual"),
    )
    db.session.add(asignatura)
    db.session.flush()
    crear_apartados_por_defecto(asignatura)
    _set_prerrequisitos(asignatura, data.get("prerrequisitos_ids"))
    db.session.commit()
    return jsonify(asignatura.to_dict()), 201


@asignaturas_bp.put("/asignaturas/<int:asignatura_id>")
def actualizar_asignatura(asignatura_id):
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}

    if "cuatrimestre_id" in data:
        Cuatrimestre.query.get_or_404(data["cuatrimestre_id"])
        asignatura.cuatrimestre_id = data["cuatrimestre_id"]
    if "nombre" in data:
        asignatura.nombre = data["nombre"]
    if "siglas" in data:
        _verificar_siglas_disponibles(data["siglas"], excluir_id=asignatura.id)
        asignatura.siglas = data["siglas"]
    if "creditos_ects" in data:
        asignatura.creditos_ects = data["creditos_ects"]
    if "tipo" in data:
        asignatura.tipo = data["tipo"]
    if "estado" in data:
        cambiar_estado_asignatura(asignatura, data["estado"], commit=False)
    if "nota_final" in data:
        asignatura.nota_final = data["nota_final"]
    if "notas" in data:
        asignatura.notas = data["notas"]
        asignatura.notas_actualizado_en = datetime.utcnow()
    if "nombre_profesor" in data:
        asignatura.nombre_profesor = data["nombre_profesor"]
    if "despacho_profesor" in data:
        asignatura.despacho_profesor = data["despacho_profesor"]
    if "correo_profesor" in data:
        asignatura.correo_profesor = data["correo_profesor"]
    if "link_aula_virtual" in data:
        asignatura.link_aula_virtual = data["link_aula_virtual"]
    if "prerrequisitos_ids" in data:
        _set_prerrequisitos(asignatura, data["prerrequisitos_ids"])

    db.session.commit()
    return jsonify(asignatura.to_dict())


@asignaturas_bp.patch("/api/asignaturas/<int:asignatura_id>/estado")
def cambiar_estado_ruta(asignatura_id):
    """
    Ruta dedicada de cambio de estado (Fase 11). Cuerpo esperado: {"estado": "cursando"}.
    Devuelve 404 si la asignatura no existe (get_or_404) y 422 si el estado no es válido
    (ver cambiar_estado_asignatura). Idempotente: repetir la misma petición no tiene
    efectos distintos a la primera vez.
    """
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    data = request.get_json(silent=True) or {}
    if "estado" not in data:
        raise ApiError("'estado' es obligatorio", 422)
    cambiar_estado_asignatura(asignatura, data["estado"])
    return jsonify(asignatura.to_dict())


@asignaturas_bp.delete("/asignaturas/<int:asignatura_id>")
def borrar_asignatura(asignatura_id):
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    borrar_carpeta_asignatura(asignatura)
    # TareaEvento no cuelga de Asignatura por relación con cascade (su asignatura_id es
    # opcional: hay tareas "generales" sin asignatura). Por eso, al borrar la asignatura,
    # sus tareas asociadas hay que eliminarlas a mano aquí; si no, quedarían huérfanas
    # apuntando a una asignatura inexistente. Solo se borran las tareas de ESTA
    # asignatura: las generales (asignatura_id NULL) no se tocan.
    # Una a una (no bulk .delete()): así SQLAlchemy dispara la cascada de cada tarea
    # a su Espacio de Estudio (models.py, cascade="all, delete-orphan"), igual que al
    # borrar una tarea suelta — un bulk delete la salta y dejaría espacios huérfanos.
    for tarea in TareaEvento.query.filter_by(asignatura_id=asignatura_id).all():
        db.session.delete(tarea)
    # HorarioClase tampoco cuelga de Asignatura por relación con cascade (su
    # asignatura_id, a diferencia del de TareaEvento, ni siquiera es opcional: toda
    # serie de horario pertenece a una asignatura). Bulk delete aquí es seguro (no
    # tiene hijos propios que dependan de ella).
    HorarioClase.query.filter_by(asignatura_id=asignatura_id).delete(synchronize_session=False)
    db.session.delete(asignatura)
    db.session.commit()
    return "", 204


# --- Gestión de optativas: catálogo + elección ---

@asignaturas_bp.get("/cuatrimestres/<int:cuatrimestre_id>/catalogo-optativas")
def catalogo_optativas(cuatrimestre_id):
    Cuatrimestre.query.get_or_404(cuatrimestre_id)
    optativas = Asignatura.query.filter_by(
        cuatrimestre_id=cuatrimestre_id, tipo="optativa", estado="no_elegida"
    ).order_by(Asignatura.nombre).all()
    return jsonify([a.to_dict(include_componentes=False) for a in optativas])


@asignaturas_bp.post("/cuatrimestres/<int:cuatrimestre_id>/optativas/elegir")
def elegir_optativa(cuatrimestre_id):
    """
    Dos modos:
    1) Elegir una opción existente del catálogo: body { "asignatura_id": <id>, "estado": "cursando"|"pendiente" }
    2) Crear una optativa nueva a mano (no estaba en el catálogo):
       body { "nombre": "...", "creditos_ects": 2, "estado": "cursando"|"pendiente" }
    """
    Cuatrimestre.query.get_or_404(cuatrimestre_id)
    data = request.get_json(silent=True) or {}
    estado_destino = data.get("estado", "pendiente")
    if estado_destino not in ("cursando", "pendiente"):
        raise ApiError("estado debe ser 'cursando' o 'pendiente' al elegir una optativa")

    if "asignatura_id" in data:
        asignatura = Asignatura.query.get_or_404(data["asignatura_id"])
        if asignatura.cuatrimestre_id != cuatrimestre_id:
            raise ApiError("la asignatura no pertenece a este cuatrimestre")
        if asignatura.tipo != "optativa":
            raise ApiError("solo se pueden elegir asignaturas de tipo optativa")
        if asignatura.estado != "no_elegida":
            raise ApiError("esta optativa ya ha sido elegida (o no está disponible en el catálogo)")
        cambiar_estado_asignatura(asignatura, estado_destino)
        return jsonify(asignatura.to_dict())

    if "nombre" in data and "creditos_ects" in data:
        asignatura = Asignatura(
            cuatrimestre_id=cuatrimestre_id,
            nombre=data["nombre"],
            creditos_ects=data["creditos_ects"],
            tipo="optativa",
            estado=estado_destino,
            origen_catalogo=False,
        )
        db.session.add(asignatura)
        db.session.flush()
        crear_apartados_por_defecto(asignatura)
        db.session.commit()
        return jsonify(asignatura.to_dict()), 201

    raise ApiError("debes indicar 'asignatura_id' (del catálogo) o 'nombre'+'creditos_ects' (nueva a mano)")


@asignaturas_bp.post("/asignaturas/<int:asignatura_id>/quitar-eleccion")
def quitar_eleccion(asignatura_id):
    """
    Revierte la elección de una optativa:
    - Si viene del catálogo del seed (origen_catalogo=True): vuelve a estado 'no_elegida' (el catálogo no se borra).
    - Si fue creada a mano (origen_catalogo=False): se borra por completo, junto a sus componentes de evaluación.
    """
    asignatura = Asignatura.query.get_or_404(asignatura_id)
    if asignatura.tipo != "optativa":
        raise ApiError("solo se puede quitar la elección de asignaturas optativas")
    if asignatura.estado == "no_elegida":
        raise ApiError("esta optativa ya está en estado no_elegida")

    if asignatura.origen_catalogo:
        # Borrar los EsquemaEvaluacion (no los componentes sueltos) para que también
        # se limpien en cascada: si no, un esquema vacío se quedaría colgado y, al
        # volver a elegir esta optativa más adelante, la ruta histórica de "añadir
        # componente" podría toparse con una ambigüedad de esquemas que no tiene
        # sentido para lo que, de cara al catálogo, vuelve a ser una ficha en blanco.
        for esquema in list(asignatura.esquemas):
            db.session.delete(esquema)
        asignatura.nota_final = None
        cambiar_estado_asignatura(asignatura, "no_elegida")
        return jsonify(asignatura.to_dict())
    else:
        borrar_carpeta_asignatura(asignatura)
        db.session.delete(asignatura)
        db.session.commit()
        return "", 204
