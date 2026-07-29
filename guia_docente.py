# -*- coding: utf-8 -*-
"""
Extracción heurística de profesorado y esquema de evaluación desde el texto de una
guía docente oficial de la UPC (PDF). 100% local: solo texto plano + regex, sin
llamadas externas ni IA.

Diseñado para nunca inventar un peso (%) que no esté explícito o no se pueda
derivar con confianza de una fórmula simple: en ese caso, el componente/esquema se
marca con "pendiente_revision": True y se deja para que el usuario lo rellene a
mano en la pantalla de confirmación (routes/guia_docente.py nunca escribe en la
BD sin pasar por esa pantalla).
"""
import re

from models import TIPOS_COMPONENTE  # noqa: F401 (referencia para quien lea el módulo)

# Cabeceras de sección tal cual aparecen en las guías docentes UPC (mayúsculas,
# consistentes entre asignaturas). Se usan para acotar cada bloque: el bloque de
# una cabecera termina en la cabecera conocida más cercana que aparezca después,
# sea cual sea (algunas guías se saltan alguna, p. ej. "CAPACIDADES PREVIAS").
CABECERAS_SECCION = (
    "PROFESORADO",
    "CAPACIDADES PREVIAS",
    "COMPETENCIAS DE LA TITULACIÓN A LAS QUE CONTRIBUYE LA ASIGNATURA",
    "METODOLOGÍAS DOCENTES",
    "OBJETIVOS DE APRENDIZAJE DE LA ASIGNATURA",
    "HORAS TOTALES DE DEDICACIÓN DEL ESTUDIANTADO",
    "CONTENIDOS",
    "SISTEMA DE CALIFICACIÓN",
    "BIBLIOGRAFÍA",
    "RECURSOS",
)

_PATRON_LINEA_GRUPO = re.compile(r"^(.+?)\s*-\s*([\d]+(?:\s*,\s*\d+)*)\s*$")
# Con dos puntos ("Examen final de teoría (EXFIN): 50%"): el nombre puede ser largo,
# el ":" ya deja claro que es una etiqueta, no una frase.
_PATRON_COMPONENTE_CON_DOSPUNTOS = re.compile(r"^(.+?):\s*(\d+(?:[.,]\d+)?)\s*%\.?\s*$")
# Sin dos puntos ("Qüestionaris quinzenals 10%"): se exige un nombre corto (máx. 5
# palabras) para no confundir con un trozo de frase partido por el salto de línea
# del PDF que termine casualmente en "... NN%." (p. ej. "...con un peso del 10%.").
_PATRON_COMPONENTE_SIN_DOSPUNTOS = re.compile(r"^([^:]+?)\s+(\d+(?:[.,]\d+)?)\s*%\.?\s*$")
_PATRON_ASIGNACION = re.compile(r"^([A-Za-zÀ-ÿ_][A-Za-zÀ-ÿ_ ]*?)\s*=\s*(.+)$")
_PATRON_TERMINO = re.compile(r"(\d+(?:[.,]\d+)?)\s*\*\s*([A-Za-zÀ-ÿ_]+)")

_TOLERANCIA_SUMA_100 = 1.5  # puntos porcentuales de margen para dar por buena una suma


def extraer_texto(ruta_absoluta):
    """Extrae el texto de todas las páginas de un PDF con pypdf (mismo extractor
    que ya usa la app para indexar documentos, ver routes/documentos.py)."""
    from pypdf import PdfReader

    lector = PdfReader(ruta_absoluta)
    return "\n".join((pagina.extract_text() or "") for pagina in lector.pages)


def _normaliza(texto):
    return re.sub(r"\s+", " ", texto or "").strip().upper()


def _extraer_seccion(texto, nombre_seccion):
    """Devuelve el contenido de una sección (sin la cabecera), acotado por la
    cabecera conocida más próxima que venga después, o None si no aparece."""
    m_inicio = re.search(rf"{re.escape(nombre_seccion)}\s*\n", texto)
    if not m_inicio:
        return None
    resto = texto[m_inicio.end():]

    fin = len(resto)
    for otra in CABECERAS_SECCION:
        if otra == nombre_seccion:
            continue
        m = re.search(rf"\n{re.escape(otra)}\s*\n", resto)
        if m and m.start() < fin:
            fin = m.start()
    return resto[:fin].strip()


def _etiqueta_grupos(grupos):
    grupos = re.sub(r"\s+", "", grupos).replace(",", ", ")
    return f"grupos {grupos}" if "," in grupos else f"grupo {grupos}"


def analizar_profesorado(texto):
    """Devuelve una lista de {"nombre", "rol"}. Lista vacía si la guía no tiene
    profesorado publicado todavía (campo "Profesorado responsable:" vacío) — nunca
    se inventa un nombre."""
    bloque = _extraer_seccion(texto, "PROFESORADO")
    if not bloque:
        return []

    # [ \t]* (no \s*) para no cruzar la línea: "Profesorado responsable:\nOtros:"
    # (responsable vacío, caso real y frecuente en guías de cuatrimestres futuros)
    # no debe capturar "Otros:" como si fuera el nombre.
    m_responsable = re.search(r"Profesorado responsable:[ \t]*([^\n]*)", bloque)
    responsable = (m_responsable.group(1).strip() if m_responsable else "") or None

    profesores = []
    if responsable:
        profesores.append({"nombre": responsable, "rol": None})

    for linea in bloque.splitlines():
        m = _PATRON_LINEA_GRUPO.match(linea.strip())
        if not m:
            continue
        nombre = m.group(1).strip()
        # descarta la propia línea "Profesorado responsable: NOMBRE" si por lo que
        # sea también matchea el patrón (no debería, no lleva "- números", pero
        # por si acaso no se duplica)
        if nombre.lower().startswith("profesorado responsable"):
            continue
        etiqueta = _etiqueta_grupos(m.group(2))

        existente = next((p for p in profesores if _normaliza(p["nombre"]) == _normaliza(nombre)), None)
        if existente:
            existente["rol"] = f"Responsable ({etiqueta})"
        else:
            profesores.append({"nombre": nombre, "rol": etiqueta.capitalize()})

    return profesores


def _inferir_tipo(nombre_componente):
    n = _normaliza((nombre_componente or "").replace("_", " "))
    if "LABORATOR" in n or "PRACTIC" in n or "PRÁCTIC" in n or re.search(r"\bLAB\b", n):
        return "laboratorio"
    if "FINAL" in n:
        return "examen_final"
    if "PARCIAL" in n or "CONTROL" in n:
        return "parcial"
    if "TEOR" in n:
        return "teoria"
    return "otro"


def _componentes_planos(bloque):
    """Caso A: líneas "Nombre: NN%" con el peso explícito. Alta confianza:
    el porcentaje viene escrito literalmente, no hay que derivarlo de nada."""
    componentes = []
    lineas_restantes = []
    for linea in bloque.splitlines():
        linea_limpia = linea.strip()
        m = _PATRON_COMPONENTE_CON_DOSPUNTOS.match(linea_limpia)
        if not m:
            m_sin = _PATRON_COMPONENTE_SIN_DOSPUNTOS.match(linea_limpia)
            if m_sin and len(m_sin.group(1).split()) <= 5:
                m = m_sin
        if m:
            nombre = m.group(1).strip()
            porcentaje = float(m.group(2).replace(",", "."))
            componentes.append({
                "nombre": nombre,
                "tipo": _inferir_tipo(nombre),
                "porcentaje": porcentaje,
                "pendiente_revision": False,
            })
        else:
            lineas_restantes.append(linea)
    return componentes, "\n".join(lineas_restantes)


def _parsear_terminos(expresion):
    """Extrae pares (coeficiente, variable) de una expresión tipo
    "0.6*Examen_final + 0.2*Examen_parcial". Devuelve None si queda texto sin
    reconocer (señal de que la expresión es más compleja de lo que sabemos leer
    con confianza), en vez de arriesgarse a ignorar un término silenciosamente."""
    terminos = []
    resto = expresion
    for m in _PATRON_TERMINO.finditer(expresion):
        terminos.append((float(m.group(1).replace(",", ".")), m.group(2)))
        resto = resto.replace(m.group(0), " ", 1)
    resto_limpio = re.sub(r"[+\-\s]", "", resto)
    if resto_limpio:
        return None  # queda texto sin explicar: no reconocemos la expresión con confianza
    return terminos


def _dividir_alternativas_max(expresion):
    """Divide el contenido de un MAX(...) por comas de nivel superior (no dentro
    de paréntesis anidados)."""
    profundidad = 0
    partes = []
    actual = []
    for c in expresion:
        if c == "(":
            profundidad += 1
        elif c == ")":
            profundidad -= 1
        if c == "," and profundidad == 0:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(c)
    partes.append("".join(actual))
    return [p.strip() for p in partes if p.strip()]


def _resolver_formula(texto_formula):
    """Caso B: fórmulas "Nota final = MAX(A, B) + C", con posible sustitución de
    UNA variable definida en otra línea del bloque (p. ej. "Nota_laboratorio =
    0.5*Examen_lab + 0.5*Proyecto"). Devuelve una lista de esquemas (uno por
    alternativa del MAX) o None si no se puede resolver con confianza.
    """
    asignaciones = {}
    orden_variables = []
    for linea in texto_formula.splitlines():
        m = _PATRON_ASIGNACION.match(linea.strip())
        if m:
            var = m.group(1).strip()
            asignaciones[_normaliza(var)] = m.group(2).strip()
            orden_variables.append(var)

    if not orden_variables:
        return None

    # La primera asignación es la fórmula principal (p. ej. "Nota final = ...")
    principal = asignaciones[_normaliza(orden_variables[0])]

    m_max = re.search(r"MAX\s*\((.+)\)(.*)", principal, re.IGNORECASE)
    if m_max:
        alternativas_max = _dividir_alternativas_max(m_max.group(1))
        cola = m_max.group(2)  # lo que se suma fuera del MAX(...), p. ej. "+ 0.4*Nota_laboratorio"
    else:
        alternativas_max = [principal]
        cola = ""

    terminos_cola = _parsear_terminos(cola) if cola.strip() else []
    if cola.strip() and terminos_cola is None:
        return None

    esquemas = []
    for i, alternativa in enumerate(alternativas_max):
        terminos = _parsear_terminos(alternativa)
        if terminos is None:
            return None
        todos = list(terminos) + list(terminos_cola)

        # Sustitución de un nivel: si una variable referenciada tiene a su vez una
        # asignación propia (y no es la fórmula principal), se sustituye por sus
        # propios términos multiplicando los coeficientes.
        expandido = []
        for coef, var in todos:
            definicion = asignaciones.get(_normaliza(var))
            if definicion and _normaliza(var) != _normaliza(orden_variables[0]):
                sub_terminos = _parsear_terminos(definicion)
                if sub_terminos is None:
                    return None
                for sub_coef, sub_var in sub_terminos:
                    expandido.append((coef * sub_coef, sub_var))
            else:
                expandido.append((coef, var))

        suma = sum(c for c, _ in expandido) * 100
        if abs(suma - 100) > _TOLERANCIA_SUMA_100:
            return None  # no cuadra: mejor no proponer números que no suman 100

        componentes = [{
            "nombre": var.replace("_", " ").strip().capitalize(),
            "tipo": _inferir_tipo(var),
            "porcentaje": round(coef * 100, 2),
            "pendiente_revision": True,  # siempre a revisar: viene de resolver una fórmula, no de un % literal
        } for coef, var in expandido]

        if len(alternativas_max) > 1:
            # El nombre se decide por CONTENIDO (qué variables tiene esta alternativa
            # del MAX), nunca por su posición/índice: la alternativa "sin parcial"
            # no siempre es la primera en la fórmula de la guía.
            tiene_parcial = any("PARCIAL" in _normaliza(var) or "CONTROL" in _normaliza(var) for _, var in expandido)
            nombre_esquema = "Con examen parcial" if tiene_parcial else "Solo examen final"
        else:
            nombre_esquema = "Evaluación"
        esquemas.append({"nombre": nombre_esquema, "componentes": componentes})

    return esquemas


def analizar_evaluacion(texto):
    """Devuelve una lista de esquemas: [{"nombre", "componentes": [...],
    "pendiente_revision": bool, "texto_sin_analizar": str|None}].

    - Si hay líneas "Nombre: NN%", se agrupan en un único esquema de alta confianza.
    - Si además/en su lugar hay una fórmula con MAX(...), se generan esquemas
      adicionales por cada alternativa (confianza media, siempre a revisar).
    - Si no se reconoce ningún % ni fórmula resoluble, se devuelve un esquema
      vacío con pendiente_revision=True y el texto crudo, para que el usuario lo
      lea y lo rellene a mano.
    """
    bloque = _extraer_seccion(texto, "SISTEMA DE CALIFICACIÓN") or _extraer_seccion(texto, "SISTEMA DE CALIFICACION")
    if not bloque:
        return []

    componentes_planos, resto = _componentes_planos(bloque)
    esquemas = []

    suma_planos = sum(c["porcentaje"] for c in componentes_planos)
    if componentes_planos and abs(suma_planos - 100) <= _TOLERANCIA_SUMA_100:
        esquemas.append({
            "nombre": "Evaluación",
            "componentes": componentes_planos,
            "pendiente_revision": False,
            "texto_sin_analizar": None,
        })
    else:
        # O no hay líneas planas, o las que hay no suman 100: probablemente son
        # coincidencias sueltas dentro de un párrafo, no una lista real de
        # componentes. Se descartan y se reintenta sobre el bloque completo en
        # vez de arriesgarse a proponer un desglose incompleto.
        resto = bloque

    esquemas_formula = _resolver_formula(resto)
    if esquemas_formula:
        for esquema in esquemas_formula:
            esquema["pendiente_revision"] = False
            esquema["texto_sin_analizar"] = None
        esquemas.extend(esquemas_formula)

    if not esquemas:
        esquemas.append({
            "nombre": "Evaluación",
            "componentes": [],
            "pendiente_revision": True,
            "texto_sin_analizar": bloque,
        })

    return esquemas


def analizar_guia_docente(texto):
    return {
        "profesores": analizar_profesorado(texto),
        "esquemas": analizar_evaluacion(texto),
    }
