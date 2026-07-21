from flask import Blueprint, request, jsonify

from models import Asignatura, Documento, PaginaTexto, TareaEvento
from routes.errors import ApiError

busqueda_bp = Blueprint("busqueda", __name__)

LIMITE_POR_GRUPO = 25


def _contiene(texto, termino):
    """Comparación case-insensitive correcta con acentos (Python, no LIKE de SQLite,
    que solo pliega mayúsculas/minúsculas de forma fiable en ASCII)."""
    return bool(texto) and termino.lower() in texto.lower()


def _fragmento(texto, termino, radio=60):
    idx = texto.lower().find(termino.lower())
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

    resultados = {"asignaturas": [], "documentos": [], "paginas_pdf": [], "notas": [], "tareas": []}

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

        for t in TareaEvento.query.all():
            if _contiene(t.titulo, termino):
                resultados["tareas"].append({
                    "id": t.id,
                    "titulo": t.titulo,
                    "fecha": t.fecha.isoformat(),
                    "url": f"/vista/calendario?anio={t.fecha.year}&mes={t.fecha.month}",
                })

        for p in PaginaTexto.query.all():
            if _contiene(p.contenido, termino):
                doc = p.documento
                resultados["paginas_pdf"].append({
                    "documento_id": doc.id,
                    "nombre_archivo": doc.nombre_archivo,
                    "asignatura_id": doc.asignatura_id,
                    "numero_pagina": p.numero_pagina,
                    "fragmento": _fragmento(p.contenido, termino),
                    "url": f"/vista/asignaturas/{doc.asignatura_id}?doc={doc.id}&pagina={p.numero_pagina}",
                })

    for d in Documento.query.all():
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
