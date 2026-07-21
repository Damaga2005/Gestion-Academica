import os
import re
import shutil
import unicodedata

from flask import current_app


def slugify(texto, max_len=60):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto).strip("_")
    return (texto or "sin_nombre")[:max_len]


def carpeta_asignatura(asignatura):
    nombre = f"{asignatura.id}_{slugify(asignatura.nombre)}"
    return os.path.join(current_app.config["DOCUMENTOS_DIR"], nombre)


def carpeta_apartado(asignatura, apartado):
    nombre = f"{apartado.id}_{slugify(apartado.nombre)}"
    return os.path.join(carpeta_asignatura(asignatura), nombre)


def carpeta_categoria(asignatura, categoria):
    """Carpeta física de una categoría fija de documentos (Fase Organización
    jerárquica). `categoria` ya viene validada contra CATEGORIAS_DOCUMENTO por el
    llamador (ver routes/errors), así que es segura como componente de ruta."""
    return os.path.join(carpeta_asignatura(asignatura), categoria)


def carpeta_grupo(asignatura, grupo):
    """Carpeta física de un subgrupo dentro de su categoría. El nombre del subgrupo
    es libre (texto del usuario), por eso se pasa por slugify + se antepone el id:
    igual que carpeta_apartado, nunca se usa el nombre en crudo como ruta."""
    nombre = f"{grupo.id}_{slugify(grupo.nombre)}"
    return os.path.join(carpeta_categoria(asignatura, grupo.categoria), nombre)


def ruta_absoluta(ruta_local):
    return os.path.join(current_app.config["DOCUMENTOS_DIR"], ruta_local)


def nombre_archivo_disponible(carpeta, nombre_original):
    """Evita colisiones: si 'x.pdf' ya existe, prueba 'x (1).pdf', 'x (2).pdf', ..."""
    base, ext = os.path.splitext(nombre_original)
    candidato = nombre_original
    contador = 1
    while os.path.exists(os.path.join(carpeta, candidato)):
        candidato = f"{base} ({contador}){ext}"
        contador += 1
    return candidato


def crear_apartados_por_defecto(asignatura):
    """Crea los 3 apartados fijos de partida (Teoría, Exámenes, Laboratorio) para una asignatura nueva."""
    from models import db, Apartado, APARTADOS_POR_DEFECTO

    for i, nombre in enumerate(APARTADOS_POR_DEFECTO):
        db.session.add(Apartado(asignatura_id=asignatura.id, nombre=nombre, orden=i))


def borrar_carpeta_asignatura(asignatura):
    """Borra del disco toda la carpeta de documentos de una asignatura (si existe)."""
    carpeta = carpeta_asignatura(asignatura)
    if os.path.isdir(carpeta):
        shutil.rmtree(carpeta, ignore_errors=True)
