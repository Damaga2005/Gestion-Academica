import os
import re
import shutil
import unicodedata

from flask import current_app
from werkzeug.utils import secure_filename

from routes.errors import ApiError

# Firmas ("magic bytes") de formatos ejecutables: se rechazan sea cual sea la
# extensión declarada, porque un atacante puede renombrar un .exe a .pdf y el
# navegador nunca es una fuente fiable de MIME/extensión.
_FIRMAS_EJECUTABLES = (
    b"MZ",  # PE/EXE, DLL (Windows)
    b"\x7fELF",  # ELF (Linux)
    b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",  # Mach-O 32/64 bits (macOS)
    b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",  # Mach-O, orden de bytes inverso
    b"\xca\xfe\xba\xbe",  # Mach-O "fat"/universal binary
)


def normalizar_busqueda(texto):
    """Pliega a minúsculas e ignora acentos/diacríticos (NFKD + descarte de
    combinantes), para que "exámen" encuentre "examen" y viceversa. Compartido por
    el indexado de PDFs (que precalcula y guarda el resultado, ver
    PaginaTexto.contenido_normalizado) y el buscador global (que lo aplica al
    término de búsqueda, mucho más corto)."""
    if not texto:
        return ""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower()


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
    """Único punto de resolución de rutas de documentos. Además de unir con
    DOCUMENTOS_DIR, comprueba que el resultado no pueda escapar de esa carpeta
    (defensa en profundidad: aunque hoy `ruta_local` siempre viene de la BD /
    de nombres ya saneados, y nunca directamente de la petición del usuario)."""
    base = os.path.realpath(current_app.config["DOCUMENTOS_DIR"])
    destino = os.path.realpath(os.path.join(base, ruta_local))
    if destino != base and not destino.startswith(base + os.sep):
        raise ApiError("Ruta de documento no permitida")
    return destino


def validar_archivo_subido(archivo):
    """Valida un FileStorage antes de guardarlo en disco (spec Fase de documentos):
    nombre no vacío tras sanear, extensión permitida, tamaño máximo, y que el
    contenido no empiece por una firma de ejecutable (independientemente de la
    extensión declarada). Nunca confía en el nombre o el MIME que envía el
    navegador. Devuelve el nombre de archivo ya saneado (`secure_filename`),
    listo para usarse como componente de ruta."""
    cfg = current_app.config

    nombre_crudo = os.path.basename(archivo.filename or "")
    nombre_seguro = secure_filename(nombre_crudo)
    if not nombre_seguro:
        raise ApiError(f"nombre de archivo no válido: '{archivo.filename}'")

    # Solo la extensión FINAL importa: "tema.1.resumen.pdf" es válido (varios puntos,
    # último segmento permitido); "informe.pdf.exe" se rechaza porque el último
    # segmento ('exe') no está permitido, no por tener más de un punto.
    extension = nombre_seguro.rsplit(".", 1)[-1].lower() if "." in nombre_seguro else ""
    if extension not in cfg["DOCUMENTO_EXTENSIONES_PERMITIDAS"]:
        raise ApiError(f"tipo de archivo no permitido: .{extension or '(sin extensión)'}")

    stream = archivo.stream
    stream.seek(0, os.SEEK_END)
    tamano = stream.tell()
    stream.seek(0)
    if tamano > cfg["DOCUMENTO_MAX_BYTES"]:
        raise ApiError(f"'{nombre_seguro}' supera el tamaño máximo permitido")

    cabecera = stream.read(8)
    stream.seek(0)
    if any(cabecera.startswith(firma) for firma in _FIRMAS_EJECUTABLES):
        raise ApiError(f"'{nombre_seguro}' parece un ejecutable: subida rechazada")

    return nombre_seguro


def validar_cantidad_archivos(archivos):
    max_archivos = current_app.config["DOCUMENTO_MAX_ARCHIVOS_POR_SUBIDA"]
    if len(archivos) > max_archivos:
        raise ApiError(f"no se pueden subir más de {max_archivos} archivos a la vez")


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
