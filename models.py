import json
import re
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates

db = SQLAlchemy()

# Validación básica de formato, no exhaustiva (no se pretende cubrir el RFC 5322 completo)
PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATRON_URL = re.compile(r"^https?://[^\s]+$")

TIPOS_ASIGNATURA = ("obligatoria", "optativa")
# Constante centralizada de estados (spec Fase 11 punto 2): única fuente de verdad
# reutilizada por el modelo, las rutas CRUD y la lógica de elección de optativas.
ESTADOS_ASIGNATURA = ("superada", "cursando", "pendiente", "no_superada", "no_elegida")
ESTADOS_CUATRIMESTRE = ("superado", "actual", "pendiente")
TIPOS_COMPONENTE = ("teoria", "parcial", "examen_final", "laboratorio", "otro")
# Regla para combinar el resultado de varios EsquemaEvaluacion de una misma asignatura
# en un único resultado "aplicable". Por ahora solo existe "maximo" (el caso típico de
# la UPC: nota final = máximo entre evaluación continua y fórmula alternativa), pero se
# deja como tupla extensible en vez de un booleano para poder añadir otras reglas
# (p. ej. "media") sin tener que tocar el esquema de datos otra vez.
REGLAS_ESQUEMA = ("maximo",)
APARTADOS_POR_DEFECTO = ("Teoría", "Exámenes", "Laboratorio")
# Categorías fijas de documentos (Fase Organización jerárquica, punto 1): no se pueden
# crear ni eliminar, toda asignatura las tiene todas implícitamente. Sustituyen a los
# Apartado como clasificador principal; Apartado se conserva en el esquema por
# compatibilidad con datos ya migrados, pero deja de usarse para documentos nuevos.
CATEGORIAS_DOCUMENTO = ("teoria", "examenes", "laboratorios", "otros")
ETIQUETA_CATEGORIA_DOCUMENTO = {
    "teoria": "Teoría", "examenes": "Exámenes", "laboratorios": "Laboratorios", "otros": "Otros",
}
# "examen" y "tarea_general" son los tipos históricos (anteriores a la Fase de
# Calendario académico y horario). Se mantienen para no romper tareas ya creadas;
# los nuevos (examen_parcial/examen_final/recuperacion/evento) son los que pide esa
# fase para poder distinguir exámenes con más detalle.
TIPOS_TAREA = (
    "examen", "examen_parcial", "examen_final", "recuperacion",
    "entrega", "tarea_general", "tutoria", "evento",
)
# Subconjunto de TIPOS_TAREA que dispara la autocreación del Espacio de Estudio
# (routes/tareas.py): programar un examen y tener que crear aparte su Espacio de
# Estudio a mano era trabajo duplicado (misma fecha/asignatura ya escrita).
TIPOS_TAREA_EXAMEN = ("examen", "examen_parcial", "examen_final", "recuperacion")
PRIORIDADES_TAREA = ("alta", "media", "baja")
TIPOS_HORARIO = ("teoria", "problemas", "laboratorio", "seminario")
DIAS_SEMANA = (1, 2, 3, 4, 5)  # 1=lunes ... 5=viernes (spec: cuadrícula lunes-viernes)
INTERVALOS_SEMANAS = (1, 2)  # 1=todas las semanas, 2=quincenal
PATRON_SIGLAS = re.compile(r"^[A-Z0-9ÁÉÍÓÚÑ]+$")
ESTADOS_HITO = ("pendiente", "en_progreso", "hecho")
WIDGETS_POR_DEFECTO = ("recordatorios", "calendario", "certificaciones", "satelite")
ORDEN_ESTADOS_CONCEPTO = ("no_visto", "flojo", "dominado")
# Días hasta la próxima revisión según nivel (repetición espaciada simplificada, spec punto 7)
INTERVALO_DIAS_CONCEPTO = {"no_visto": 0, "flojo": 3, "dominado": 18}
# Secciones fijas de un Espacio de Estudio (spec "Espacios de Estudio Inteligentes"):
# los documentos se referencian, nunca se copian ni se mueven de su ubicación original.
# "Material importante" no es una sección propia: es una vista filtrada de las
# referencias con destacado=True (ver EspacioEstudioDocumento).
SECCIONES_ESPACIO_ESTUDIO = ("examenes_anteriores", "teoria", "ejercicios", "laboratorio")
# Tipos de entidad indexables por la búsqueda global (V2.1): identifican qué modelo/tabla
# referencia entidad_id en BusquedaFavorito/BusquedaReciente, ya que ambas tablas son
# genéricas y no tienen una FK real a cada tabla posible.
TIPOS_ENTIDAD_BUSQUEDA = (
    "asignatura", "profesor", "documento", "pagina_pdf", "tarea", "examen", "evento", "etiqueta",
    "hito", "concepto", "nota_al_vuelo",
)
# Nota de corte del indicador visual "Estado de las Asignaturas" (🟢/🟡/🔴/⚪),
# calculado solo a partir de las notas: no toca ni depende del campo `estado`
# manual de Asignatura (cursando/superada/pendiente/no_superada/no_elegida),
# que nunca ha exigido nota para marcarse (ver cambiar_estado_asignatura).
NOTA_MINIMA_APROBADO = 5.0


# Tabla de asociación many-to-many para prerrequisitos (auto-referencial sobre Asignatura)
asignatura_prerrequisito = db.Table(
    "asignatura_prerrequisito",
    db.Column("asignatura_id", db.Integer, db.ForeignKey("asignatura.id"), primary_key=True),
    db.Column("prerrequisito_id", db.Integer, db.ForeignKey("asignatura.id"), primary_key=True),
)


class Anio(db.Model):
    __tablename__ = "anio"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False, unique=True)  # 1-4

    cuatrimestres = db.relationship(
        "Cuatrimestre", back_populates="anio", cascade="all, delete-orphan", order_by="Cuatrimestre.numero"
    )

    @validates("numero")
    def validar_numero(self, key, value):
        if value is None or not (1 <= int(value) <= 4):
            raise ValueError("numero de Año debe estar entre 1 y 4")
        return value

    def to_dict(self, include_cuatrimestres=False):
        data = {"id": self.id, "numero": self.numero}
        if include_cuatrimestres:
            data["cuatrimestres"] = [c.to_dict() for c in self.cuatrimestres]
        return data


class Cuatrimestre(db.Model):
    __tablename__ = "cuatrimestre"

    id = db.Column(db.Integer, primary_key=True)
    anio_id = db.Column(db.Integer, db.ForeignKey("anio.id"), nullable=False)
    numero = db.Column(db.Integer, nullable=False, unique=True)  # 1-8 global
    estado = db.Column(db.String(20), nullable=False, default="pendiente")

    anio = db.relationship("Anio", back_populates="cuatrimestres")
    asignaturas = db.relationship(
        "Asignatura", back_populates="cuatrimestre", cascade="all, delete-orphan", order_by="Asignatura.nombre"
    )

    @validates("numero")
    def validar_numero(self, key, value):
        if value is None or not (1 <= int(value) <= 8):
            raise ValueError("numero de Cuatrimestre debe estar entre 1 y 8")
        return value

    @validates("estado")
    def validar_estado(self, key, value):
        if value not in ESTADOS_CUATRIMESTRE:
            raise ValueError(f"estado de Cuatrimestre debe ser uno de {ESTADOS_CUATRIMESTRE}")
        return value

    def to_dict(self, include_asignaturas=True):
        data = {
            "id": self.id,
            "anio_id": self.anio_id,
            "numero": self.numero,
            "estado": self.estado,
        }
        if include_asignaturas:
            data["asignaturas"] = [a.to_dict(include_componentes=False) for a in self.asignaturas]
        return data


class Asignatura(db.Model):
    __tablename__ = "asignatura"

    id = db.Column(db.Integer, primary_key=True)
    cuatrimestre_id = db.Column(db.Integer, db.ForeignKey("cuatrimestre.id"), nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    # Código oficial del plan de estudios (p. ej. "DSED"). Nullable a nivel de columna
    # a propósito (spec Fase Calendario/Horario punto 10): las asignaturas ya cargadas
    # no tienen por qué tener siglas conocidas todavía, y no hay que inventárselas. La
    # restricción UNIQUE sí aplica desde ya (SQLite permite varios NULL en una columna
    # UNIQUE sin conflicto entre ellos).
    siglas = db.Column(db.String(20), unique=True, nullable=True)
    creditos_ects = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default="obligatoria")
    estado = db.Column(db.String(20), nullable=False, default="pendiente")
    nota_final = db.Column(db.Float, nullable=True)
    # True si la fila viene del catálogo de optativas cargado en el seed.
    # Determina si "quitar elección" la revierte a no_elegida (True) o la borra (False, creada a mano).
    origen_catalogo = db.Column(db.Boolean, nullable=False, default=False)
    # Regla para combinar el resultado de los esquemas de evaluación cuando hay más de
    # uno (ver REGLAS_ESQUEMA). Con un solo esquema (el caso normal) no tiene efecto.
    regla_esquemas = db.Column(db.String(20), nullable=False, default="maximo")
    notas = db.Column(db.Text, nullable=True)  # notas rápidas de texto libre (spec punto 3)
    notas_actualizado_en = db.Column(db.DateTime, nullable=True)  # para detectar inactividad (spec punto 6)

    # Metadatos de contacto/logística del profesor (Fase 11), todos opcionales
    nombre_profesor = db.Column(db.String(200), nullable=True)
    despacho_profesor = db.Column(db.String(200), nullable=True)
    correo_profesor = db.Column(db.String(200), nullable=True)
    link_aula_virtual = db.Column(db.String(500), nullable=True)

    cuatrimestre = db.relationship("Cuatrimestre", back_populates="asignaturas")
    componentes = db.relationship(
        "ComponenteEvaluacion", back_populates="asignatura", cascade="all, delete-orphan"
    )
    esquemas = db.relationship(
        "EsquemaEvaluacion", back_populates="asignatura", cascade="all, delete-orphan",
        order_by="EsquemaEvaluacion.orden"
    )
    apartados = db.relationship(
        "Apartado", back_populates="asignatura", cascade="all, delete-orphan", order_by="Apartado.orden"
    )
    documentos = db.relationship(
        "Documento", back_populates="asignatura", cascade="all, delete-orphan"
    )
    grupos_documento = db.relationship(
        "GrupoDocumento", back_populates="asignatura", cascade="all, delete-orphan",
        order_by="GrupoDocumento.orden"
    )
    conceptos = db.relationship(
        "Concepto", back_populates="asignatura", cascade="all, delete-orphan"
    )
    recursos_externos = db.relationship(
        "RecursoExterno", back_populates="asignatura", cascade="all, delete-orphan",
        order_by="RecursoExterno.orden"
    )
    profesores = db.relationship(
        "Profesor", back_populates="asignatura", cascade="all, delete-orphan",
        order_by="Profesor.orden"
    )

    prerrequisitos = db.relationship(
        "Asignatura",
        secondary=asignatura_prerrequisito,
        primaryjoin=id == asignatura_prerrequisito.c.asignatura_id,
        secondaryjoin=id == asignatura_prerrequisito.c.prerrequisito_id,
        backref="es_prerrequisito_de",
    )

    @validates("tipo")
    def validar_tipo(self, key, value):
        if value not in TIPOS_ASIGNATURA:
            raise ValueError(f"tipo de Asignatura debe ser uno de {TIPOS_ASIGNATURA}")
        return value

    @validates("siglas")
    def validar_siglas(self, key, value):
        """Normaliza (recorta espacios y pasa a mayúsculas) antes de guardar. None/""
        se guardan como NULL: unas siglas vacías no son un valor válido, son "sin
        siglas todavía", así que no tiene sentido guardar una cadena vacía distinta."""
        if value is None:
            return None
        limpio = value.strip().upper()
        if not limpio:
            return None
        if not PATRON_SIGLAS.match(limpio):
            raise ValueError("siglas solo puede contener letras, números y sin espacios")
        return limpio

    @validates("regla_esquemas")
    def validar_regla_esquemas(self, key, value):
        if value not in REGLAS_ESQUEMA:
            raise ValueError(f"regla_esquemas debe ser una de {REGLAS_ESQUEMA}")
        return value

    @validates("estado")
    def validar_estado(self, key, value):
        if value not in ESTADOS_ASIGNATURA:
            raise ValueError(f"estado de Asignatura debe ser uno de {ESTADOS_ASIGNATURA}")
        return value

    @validates("correo_profesor")
    def validar_correo_profesor(self, key, value):
        if value and not PATRON_EMAIL.match(value.strip()):
            raise ValueError("correo_profesor no tiene un formato de email válido")
        return value

    @validates("link_aula_virtual")
    def validar_link_aula_virtual(self, key, value):
        if value and not PATRON_URL.match(value.strip()):
            raise ValueError("link_aula_virtual debe ser una URL http(s) válida")
        return value

    def to_dict(self, include_componentes=True):
        prerrequisitos_cumplidos = all(p.estado == "superada" for p in self.prerrequisitos)
        data = {
            "id": self.id,
            "cuatrimestre_id": self.cuatrimestre_id,
            "nombre": self.nombre,
            "siglas": self.siglas,
            "creditos_ects": self.creditos_ects,
            "tipo": self.tipo,
            "estado": self.estado,
            "nota_final": self.nota_final,
            "origen_catalogo": self.origen_catalogo,
            "regla_esquemas": self.regla_esquemas,
            "notas": self.notas,
            "notas_actualizado_en": self.notas_actualizado_en.isoformat() if self.notas_actualizado_en else None,
            "nombre_profesor": self.nombre_profesor,
            "despacho_profesor": self.despacho_profesor,
            "correo_profesor": self.correo_profesor,
            "link_aula_virtual": self.link_aula_virtual,
            "recursos_externos": [r.to_dict() for r in self.recursos_externos],
            "profesores": [p.to_dict() for p in self.profesores],
            "prerrequisitos": [{"id": p.id, "nombre": p.nombre} for p in self.prerrequisitos],
            "prerrequisitos_cumplidos": prerrequisitos_cumplidos,
            **calcular_estado_notas(self),
        }
        if include_componentes:
            data["componentes"] = [c.to_dict() for c in self.componentes]
            data["esquemas"] = esquemas_con_ganador(self.esquemas, self.regla_esquemas)
        return data


def resolver_asignatura(identificador):
    """
    Localiza una Asignatura por su id numérico interno O por sus siglas oficiales
    (spec Fase Calendario/Horario punto 1): la API acepta ambos de cara afuera, pero
    todas las relaciones internas (claves foráneas) siguen usando el id numérico —
    esta función es el único punto donde se resuelve la sigla al id antes de tocar
    la base de datos.

    Devuelve None si no encuentra nada (el llamador decide si eso es 404 o "opcional").
    """
    if identificador is None:
        return None
    texto = str(identificador).strip()
    if not texto:
        return None
    if texto.isdigit():
        return db.session.get(Asignatura, int(texto))
    return Asignatura.query.filter_by(siglas=texto.upper()).first()


class ComponenteEvaluacion(db.Model):
    __tablename__ = "componente_evaluacion"

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=False)
    # A qué EsquemaEvaluacion pertenece este componente. Nullable a nivel de columna solo
    # por compatibilidad con la migración (que rellena esta columna en asignaturas ya
    # existentes); en la práctica toda fila creada por la app siempre tiene un esquema.
    esquema_id = db.Column(db.Integer, db.ForeignKey("esquema_evaluacion.id"), nullable=True)
    # Si pertenece a un Bloque (spec "nota jerárquica", p. ej. Laboratorio = 40% de la
    # nota final, calculado a su vez a partir de prácticas/controles): el porcentaje de
    # este componente es relativo al bloque, no al esquema completo. NULL = componente
    # "suelto" de siempre, directo sobre el 100% del esquema (comportamiento sin cambios).
    bloque_id = db.Column(db.Integer, db.ForeignKey("bloque_evaluacion.id"), nullable=True)
    nombre = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default="otro")
    porcentaje = db.Column(db.Float, nullable=False)
    nota = db.Column(db.Float, nullable=True)
    # Nota mínima exigida en este componente para poder aprobar la asignatura (p. ej. un
    # 4 en el examen final, aunque la media ponderada llegue a 5). NULL = sin mínimo.
    nota_minima = db.Column(db.Float, nullable=True)
    # Los nuevos van al final (valor alto); mover_en_lista renumera 0..n-1 al reordenar.
    orden = db.Column(db.Integer, nullable=False, default=1_000_000)

    asignatura = db.relationship("Asignatura", back_populates="componentes")
    esquema = db.relationship("EsquemaEvaluacion", back_populates="componentes")
    bloque = db.relationship("BloqueEvaluacion", back_populates="componentes")

    @validates("tipo")
    def validar_tipo(self, key, value):
        if value not in TIPOS_COMPONENTE:
            raise ValueError(f"tipo de Componente debe ser uno de {TIPOS_COMPONENTE}")
        return value

    @validates("porcentaje")
    def validar_porcentaje(self, key, value):
        if value is None or not (0 <= float(value) <= 100):
            raise ValueError("porcentaje debe estar entre 0 y 100")
        return value

    @validates("nota_minima")
    def validar_nota_minima(self, key, value):
        if value is not None and not (0 <= float(value) <= 10):
            raise ValueError("nota_minima debe estar entre 0 y 10")
        return value

    def incumple_minimo(self):
        return self.nota is not None and self.nota_minima is not None and self.nota < self.nota_minima

    def to_dict(self):
        return {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "esquema_id": self.esquema_id,
            "bloque_id": self.bloque_id,
            "nombre": self.nombre,
            "tipo": self.tipo,
            "porcentaje": self.porcentaje,
            "nota": self.nota,
            "nota_minima": self.nota_minima,
        }


class BloqueEvaluacion(db.Model):
    """
    Grupo de componentes dentro de un EsquemaEvaluacion cuya propia nota se calcula a
    partir de sus componentes (p. ej. "Laboratorio" pesa 40% de la nota final, y esa
    nota de Laboratorio sale a su vez de una media ponderada de prácticas/controles).
    Un nivel de anidamiento (no bloques dentro de bloques): cubre el caso real de las
    guías docentes de la UPC sin la complejidad de un árbol genérico.
    """
    __tablename__ = "bloque_evaluacion"

    id = db.Column(db.Integer, primary_key=True)
    esquema_id = db.Column(db.Integer, db.ForeignKey("esquema_evaluacion.id"), nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    porcentaje = db.Column(db.Float, nullable=False)
    orden = db.Column(db.Integer, nullable=False, default=0)

    esquema = db.relationship("EsquemaEvaluacion", back_populates="bloques")
    componentes = db.relationship(
        "ComponenteEvaluacion", back_populates="bloque", cascade="all, delete-orphan",
        order_by="(ComponenteEvaluacion.orden, ComponenteEvaluacion.id)"
    )

    @validates("porcentaje")
    def validar_porcentaje(self, key, value):
        if value is None or not (0 <= float(value) <= 100):
            raise ValueError("porcentaje debe estar entre 0 y 100")
        return value

    def to_dict(self, incluir_componentes=True):
        data = {
            "id": self.id,
            "esquema_id": self.esquema_id,
            "nombre": self.nombre,
            "porcentaje": self.porcentaje,
            "orden": self.orden,
            "resultado": calcular_resultado_componentes(self.componentes),
        }
        if incluir_componentes:
            data["componentes"] = [c.to_dict() for c in self.componentes]
        return data


def mover_en_lista(items, item, direccion):
    """Sube ("arriba") o baja ("abajo") `item` dentro de `items` (ya en su orden actual)
    y renumera `orden` como 0..n-1. Sin efecto en los extremos."""
    lista = list(items)
    i = lista.index(item)
    j = i - 1 if direccion == "arriba" else i + 1
    if 0 <= j < len(lista):
        lista[i], lista[j] = lista[j], lista[i]
    for n, it in enumerate(lista):
        it.orden = n


def calcular_resultado_componentes(componentes):
    """
    Resultado agregado de una lista de ComponenteEvaluacion (independiente de si
    pertenecen a un único esquema "de siempre" o a uno de varios EsquemaEvaluacion):
    - peso_total: suma de porcentajes de todos los componentes.
    - peso_evaluado / porcentaje_evaluado: cuánto de ese peso ya tiene nota puesta.
    - media_ponderada: nota media ponderada SOLO de los componentes con nota (None si
      ninguno la tiene todavía) — mismo criterio que ya usaba la vista de un único
      esquema, no una proyección sobre el 100% del peso.
    """
    con_nota = [c for c in componentes if c.nota is not None]
    peso_total = sum(c.porcentaje for c in componentes)
    peso_evaluado = sum(c.porcentaje for c in con_nota)
    porcentaje_evaluado = round((peso_evaluado / peso_total) * 100, 2) if peso_total else 0.0

    media_ponderada = None
    if con_nota and peso_evaluado > 0:
        media_ponderada = round(sum(c.porcentaje * c.nota for c in con_nota) / peso_evaluado, 4)

    return {
        "peso_total": peso_total,
        "peso_evaluado": peso_evaluado,
        "porcentaje_evaluado": porcentaje_evaluado,
        "media_ponderada": media_ponderada,
    }


class EsquemaEvaluacion(db.Model):
    """
    Fórmula de evaluación alternativa dentro de una asignatura (p. ej. "Evaluación
    continua" vs "Fórmula con más peso al examen final", habitual en la UPC). La
    mayoría de asignaturas tienen exactamente un esquema; cuando hay más de uno, la
    nota que cuenta es la que da el mejor resultado según `Asignatura.regla_esquemas`.
    """
    __tablename__ = "esquema_evaluacion"

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    orden = db.Column(db.Integer, nullable=False, default=0)

    asignatura = db.relationship("Asignatura", back_populates="esquemas")
    componentes = db.relationship(
        "ComponenteEvaluacion", back_populates="esquema", cascade="all, delete-orphan",
        order_by="(ComponenteEvaluacion.orden, ComponenteEvaluacion.id)"
    )
    bloques = db.relationship(
        "BloqueEvaluacion", back_populates="esquema", cascade="all, delete-orphan",
        order_by="BloqueEvaluacion.orden"
    )

    def componentes_efectivos_objs(self):
        """Sueltos + un objeto virtual por bloque (con su nota ya agregada): lo que de
        verdad pesa sobre el 100% del esquema. Los hijos de un bloque NO van aquí."""
        sueltos = [c for c in self.componentes if c.bloque_id is None]
        return sueltos + [
            SimpleNamespace(porcentaje=b.porcentaje, nota=calcular_resultado_componentes(b.componentes)["media_ponderada"])
            for b in self.bloques
        ]

    def to_dict(self, incluir_componentes=True):
        # "Sueltos": componentes directos sobre el 100% del esquema (comportamiento de
        # siempre). Cada bloque cuenta como un componente más de cara al resultado del
        # esquema, con su propia nota ya calculada (None si el bloque no tiene ninguna
        # nota puesta todavía) — así un esquema sin bloques se comporta exactamente
        # igual que antes, y calcular_resultado_componentes no necesita saber nada de
        # bloques (solo lee .porcentaje/.nota, que SimpleNamespace también expone).
        sueltos = [c for c in self.componentes if c.bloque_id is None]
        bloques_dict = [b.to_dict() for b in self.bloques]
        bloques_como_componente = [
            SimpleNamespace(porcentaje=b.porcentaje, nota=bd["resultado"]["media_ponderada"])
            for b, bd in zip(self.bloques, bloques_dict)
        ]
        resultado = calcular_resultado_componentes(sueltos + bloques_como_componente)
        data = {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "nombre": self.nombre,
            "orden": self.orden,
            "resultado": resultado,
        }
        if incluir_componentes:
            componentes_sueltos_dict = [c.to_dict() for c in sueltos]
            data["componentes"] = componentes_sueltos_dict
            data["bloques"] = bloques_dict
            # Lista plana combinada (sueltos + un "componente" virtual por bloque, con
            # su nota ya agregada) para reutilizar tal cual la calculadora de "¿qué nota
            # necesito?" y la tabla comparativa de esquemas, sin que tengan que saber
            # distinguir un bloque de un componente normal.
            data["componentes_efectivos"] = componentes_sueltos_dict + [
                {
                    "id": f"bloque-{b.id}", "bloque_id": b.id, "es_bloque": True,
                    "nombre": b.nombre, "tipo": "bloque",
                    "porcentaje": b.porcentaje, "nota": bd["resultado"]["media_ponderada"],
                }
                for b, bd in zip(self.bloques, bloques_dict)
            ]
        return data


def esquemas_con_ganador(esquemas, regla):
    """
    Serializa la lista de EsquemaEvaluacion de una asignatura añadiendo a cada uno un
    flag "aplicado": cuál es el que cuenta según `regla` (de momento solo "maximo").

    - 0 ó 1 esquema: no hay comparación que hacer; ese único esquema (si existe) queda
      marcado como aplicado, ya que es el único resultado posible.
    - Varios esquemas: aplicado = el de mayor media_ponderada actual entre los que ya
      tienen alguna nota puesta. Si ninguno tiene nota todavía, no se marca ninguno
      (no hay base para decidir un "ganador" con puros ceros).
    """
    lista = [e.to_dict(incluir_componentes=True) for e in esquemas]

    if len(lista) <= 1:
        for e in lista:
            e["aplicado"] = True
        return lista

    if regla == "maximo":
        candidatos = [e for e in lista if e["resultado"]["media_ponderada"] is not None]
        ganador_id = max(candidatos, key=lambda e: e["resultado"]["media_ponderada"])["id"] if candidatos else None
        for e in lista:
            e["aplicado"] = (e["id"] == ganador_id)
        return lista

    for e in lista:
        e["aplicado"] = False
    return lista


def calcular_estado_notas(asignatura):
    """
    Indicador visual "Estado de las Asignaturas" (🟢 Aprobada / 🟡 En progreso /
    🔴 Suspendida / ⚪ Sin evaluar), calculado solo a partir de las notas —
    independiente del campo `estado` manual (ver NOTA_MINIMA_APROBADO).

    Prioridad: nota_final (override manual, ver Asignatura.nota_final) por
    encima de cualquier cálculo por componentes, igual que ya hace la ficha de
    asignatura para las que no tienen desglose claro. Si no hay nota_final, se
    usa el esquema con mejor media_ponderada (misma regla "maximo" que
    esquemas_con_ganador) y solo se da por evaluada si ese esquema tiene el
    100% del peso puntuado (comparando pesos en crudo, no el porcentaje ya
    redondeado, para evitar falsos negativos por redondeo).
    """
    evaluaciones_realizadas = 0
    evaluaciones_pendientes = 0
    porcentaje_evaluado = 0.0
    minimo_incumplido = False  # algún componente con nota_minima por debajo de ella (esquema aplicado)

    if asignatura.nota_final is not None:
        nota = asignatura.nota_final
        evaluada = True
        componentes = [c for e in asignatura.esquemas for c in e.componentes_efectivos_objs()] or asignatura.componentes
        evaluaciones_realizadas = sum(1 for c in componentes if c.nota is not None)
        evaluaciones_pendientes = sum(1 for c in componentes if c.nota is None)
        porcentaje_evaluado = 100.0
    else:
        nota = None
        evaluada = False
        resultados = [(e, calcular_resultado_componentes(e.componentes_efectivos_objs())) for e in asignatura.esquemas]
        candidatos = [(e, r) for e, r in resultados if r["media_ponderada"] is not None]

        if candidatos:
            esquema, resultado = max(candidatos, key=lambda par: par[1]["media_ponderada"])
            porcentaje_evaluado = resultado["porcentaje_evaluado"]
            minimo_incumplido = any(c.incumple_minimo() for c in esquema.componentes)
            efectivos = esquema.componentes_efectivos_objs()
            evaluaciones_realizadas = sum(1 for c in efectivos if c.nota is not None)
            evaluaciones_pendientes = sum(1 for c in efectivos if c.nota is None)
            if resultado["peso_total"] > 0 and resultado["peso_evaluado"] >= resultado["peso_total"]:
                nota = resultado["media_ponderada"]
                evaluada = True

    if evaluada:
        estado_notas = "aprobada" if nota >= NOTA_MINIMA_APROBADO and not minimo_incumplido else "suspendida"
    elif evaluaciones_realizadas > 0:
        estado_notas = "en_progreso"
    else:
        estado_notas = "sin_evaluar"

    return {
        "estado_notas": estado_notas,
        "nota_actual": nota,
        "evaluaciones_realizadas": evaluaciones_realizadas,
        "evaluaciones_pendientes": evaluaciones_pendientes,
        "porcentaje_evaluado": porcentaje_evaluado,
        "minimo_incumplido": minimo_incumplido,
    }


class Apartado(db.Model):
    __tablename__ = "apartado"

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    orden = db.Column(db.Integer, nullable=False, default=0)

    asignatura = db.relationship("Asignatura", back_populates="apartados")
    documentos = db.relationship(
        "Documento", back_populates="apartado", cascade="all, delete-orphan", order_by="Documento.nombre_archivo"
    )

    def to_dict(self, include_documentos=False):
        data = {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "nombre": self.nombre,
            "orden": self.orden,
        }
        if include_documentos:
            data["documentos"] = [d.to_dict() for d in self.documentos]
        return data


class GrupoDocumento(db.Model):
    """
    Subgrupo libre dentro de una categoría fija de documentos (Fase Organización
    jerárquica, punto 2). P. ej. categoria="teoria", nombre="Tema 1". El nombre debe
    ser único dentro de (asignatura, categoria) — normalizado (espacios recortados y
    colapsados) para que "Tema  1" y "Tema 1" cuenten como el mismo nombre —, pero se
    puede repetir libremente en otra categoría o en otra asignatura.
    """
    __tablename__ = "grupo_documento"
    __table_args__ = (
        db.UniqueConstraint("asignatura_id", "categoria", "nombre", name="uq_grupo_documento_asig_cat_nombre"),
    )

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=False)
    categoria = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    orden = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    asignatura = db.relationship("Asignatura", back_populates="grupos_documento")
    documentos = db.relationship(
        "Documento", back_populates="grupo", order_by="Documento.nombre_archivo"
    )

    @validates("categoria")
    def validar_categoria(self, key, value):
        if value not in CATEGORIAS_DOCUMENTO:
            raise ValueError(f"categoria debe ser una de {CATEGORIAS_DOCUMENTO}")
        return value

    @validates("nombre")
    def validar_nombre(self, key, value):
        # Normaliza espacios (recorta y colapsa múltiples espacios en uno) antes de
        # guardar: es lo que hace que la comprobación de duplicados y el UNIQUE de BD
        # traten "Tema  1" y " Tema 1 " como el mismo nombre.
        limpio = re.sub(r"\s+", " ", (value or "")).strip()
        if not limpio:
            raise ValueError("nombre de GrupoDocumento no puede estar vacío")
        return limpio

    def to_dict(self):
        return {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "categoria": self.categoria,
            "nombre": self.nombre,
            "orden": self.orden,
            "total_documentos": len(self.documentos),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Documento(db.Model):
    __tablename__ = "documento"

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=False, index=True)
    # Legado (previo a la Fase de Organización jerárquica): nullable a partir de esa
    # fase porque los documentos nuevos ya no se clasifican por Apartado, sino por
    # categoria + grupo_documento_id. Se conserva sin más en los documentos migrados.
    apartado_id = db.Column(db.Integer, db.ForeignKey("apartado.id"), nullable=True, index=True)
    # Categoría fija (obligatoria en la práctica; nullable a nivel de columna solo
    # para permitir el backfill de la migración sin bloquear filas ya existentes).
    categoria = db.Column(db.String(20), nullable=True)
    grupo_documento_id = db.Column(db.Integer, db.ForeignKey("grupo_documento.id"), nullable=True, index=True)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    # Nombre tal cual lo envió el navegador al subir el archivo, solo para auditoría/
    # trazabilidad: nunca se usa para construir una ruta en disco (eso es nombre_archivo
    # tras sanear + nombre_archivo_disponible) y siempre se escapa al mostrarlo.
    nombre_original = db.Column(db.String(255), nullable=True)
    ruta_local = db.Column(db.String(500), nullable=False)  # relativa a config.DOCUMENTOS_DIR
    tamano_bytes = db.Column(db.Integer, nullable=True)
    fecha_subida = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ultima_pagina_vista = db.Column(db.Integer, nullable=True)
    etiquetas = db.Column(db.String(500), nullable=True)  # lista libre separada por comas

    # "Continúa donde lo dejaste": estado de lectura del visor PDF, ampliando
    # ultima_pagina_vista (que ya se usaba para el deep-link del buscador y no se toca).
    porcentaje_leido = db.Column(db.Float, nullable=True)
    zoom_nivel = db.Column(db.String(20), nullable=True)  # p.ej. "page-width", "1.25"
    modo_visualizacion = db.Column(db.String(20), nullable=True)  # scrollMode/spreadMode de pdf.js
    scroll_vertical = db.Column(db.Float, nullable=True)
    fecha_primera_apertura = db.Column(db.DateTime, nullable=True)
    fecha_ultima_apertura = db.Column(db.DateTime, nullable=True, index=True)
    tiempo_total_lectura_segundos = db.Column(db.Integer, nullable=False, default=0)
    numero_sesiones = db.Column(db.Integer, nullable=False, default=0)

    asignatura = db.relationship("Asignatura", back_populates="documentos")
    apartado = db.relationship("Apartado", back_populates="documentos")
    grupo = db.relationship("GrupoDocumento", back_populates="documentos")
    marcadores = db.relationship(
        "Marcador", back_populates="documento", cascade="all, delete-orphan", order_by="Marcador.numero_pagina"
    )
    paginas_texto = db.relationship(
        "PaginaTexto", back_populates="documento", cascade="all, delete-orphan"
    )
    anotaciones = db.relationship(
        "AnotacionPdf", back_populates="documento", cascade="all, delete-orphan",
        order_by="AnotacionPdf.numero_pagina",
    )
    # Borrar el documento borra también las referencias a él en Espacios de Estudio
    # (la fila de referencia, nunca otro documento: mismo patrón que arriba).
    referencias_espacio_estudio = db.relationship(
        "EspacioEstudioDocumento", back_populates="documento", cascade="all, delete-orphan"
    )

    EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png", ".gif", ".webp")

    @validates("categoria")
    def validar_categoria(self, key, value):
        if value is not None and value not in CATEGORIAS_DOCUMENTO:
            raise ValueError(f"categoria debe ser una de {CATEGORIAS_DOCUMENTO}")
        return value

    def es_pdf(self):
        return self.nombre_archivo.lower().endswith(".pdf")

    def es_imagen(self):
        return self.nombre_archivo.lower().endswith(self.EXTENSIONES_IMAGEN)

    def lista_etiquetas(self):
        if not self.etiquetas:
            return []
        return [e.strip() for e in self.etiquetas.split(",") if e.strip()]

    def to_dict(self, include_marcadores=False):
        data = {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "apartado_id": self.apartado_id,
            "categoria": self.categoria,
            "grupo_documento_id": self.grupo_documento_id,
            "nombre_archivo": self.nombre_archivo,
            "nombre_original": self.nombre_original,
            "tamano_bytes": self.tamano_bytes,
            "fecha_subida": self.fecha_subida.isoformat(),
            "es_pdf": self.es_pdf(),
            "es_imagen": self.es_imagen(),
            "ultima_pagina_vista": self.ultima_pagina_vista,
            "etiquetas": self.lista_etiquetas(),
            "porcentaje_leido": self.porcentaje_leido,
            "zoom_nivel": self.zoom_nivel,
            "modo_visualizacion": self.modo_visualizacion,
            "scroll_vertical": self.scroll_vertical,
            "fecha_primera_apertura": self.fecha_primera_apertura.isoformat() if self.fecha_primera_apertura else None,
            "fecha_ultima_apertura": self.fecha_ultima_apertura.isoformat() if self.fecha_ultima_apertura else None,
            "tiempo_total_lectura_segundos": self.tiempo_total_lectura_segundos,
            "numero_sesiones": self.numero_sesiones,
            "total_paginas": len(self.paginas_texto) if self.paginas_texto else None,
        }
        if include_marcadores:
            data["marcadores"] = [m.to_dict() for m in self.marcadores]
        return data


class Marcador(db.Model):
    __tablename__ = "marcador"

    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey("documento.id"), nullable=False)
    numero_pagina = db.Column(db.Integer, nullable=False)
    titulo = db.Column(db.String(200), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    documento = db.relationship("Documento", back_populates="marcadores")

    @validates("numero_pagina")
    def validar_pagina(self, key, value):
        if value is None or int(value) < 1:
            raise ValueError("numero_pagina debe ser mayor o igual que 1")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "documento_id": self.documento_id,
            "numero_pagina": self.numero_pagina,
            "titulo": self.titulo,
            "fecha_creacion": self.fecha_creacion.isoformat(),
        }


TIPOS_ANOTACION_PDF = ("resaltado", "subrayado", "tachado", "nota")


class AnotacionPdf(db.Model):
    """Resaltados/subrayados/tachados sobre el texto de un PDF, al estilo de los
    lectores habituales (Acrobat, Preview, el visor de Chrome…).

    La geometría se guarda en `rects` como JSON: una lista de rectángulos
    [x, y, ancho, alto] con valores 0..1 relativos al tamaño de la página. Al ser
    relativos, la anotación se coloca igual con cualquier zoom o tamaño de ventana
    sin recalcular nada, que es justo lo que hace falta para que no "baile" al
    hacer zoom. Se guardan varios rectángulos porque una selección que abarca
    varias líneas necesita una barra por línea."""

    __tablename__ = "anotacion_pdf"

    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(
        db.Integer, db.ForeignKey("documento.id"), nullable=False, index=True
    )
    numero_pagina = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default="resaltado")
    color = db.Column(db.String(20), nullable=False, default="#ffd400")
    # Texto seleccionado, para poder listar las anotaciones y copiarlas sin
    # tener que volver a abrir la página del PDF.
    texto = db.Column(db.Text, nullable=True)
    comentario = db.Column(db.Text, nullable=True)
    rects = db.Column(db.Text, nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    documento = db.relationship("Documento", back_populates="anotaciones")

    @validates("tipo")
    def validar_tipo(self, key, value):
        if value not in TIPOS_ANOTACION_PDF:
            raise ValueError(f"tipo debe ser uno de {TIPOS_ANOTACION_PDF}")
        return value

    @validates("numero_pagina")
    def validar_pagina(self, key, value):
        if value is None or int(value) < 1:
            raise ValueError("numero_pagina debe ser mayor o igual que 1")
        return value

    def to_dict(self):
        try:
            rects = json.loads(self.rects)
        except (TypeError, ValueError):
            rects = []
        return {
            "id": self.id,
            "documento_id": self.documento_id,
            "numero_pagina": self.numero_pagina,
            "tipo": self.tipo,
            "color": self.color,
            "texto": self.texto,
            "comentario": self.comentario,
            "rects": rects,
            "fecha_creacion": self.fecha_creacion.isoformat(),
        }


class TareaEvento(db.Model):
    """Entidad del calendario académico: exámenes, entregas, tutorías y eventos
    puntuales. Los campos de horario/aula/etc. son opcionales porque las tareas
    "de siempre" (tarea_general, entregas sin hora fija) no los necesitan."""
    __tablename__ = "tarea_evento"

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=True, index=True)
    # Integración con el visor PDF (spec V2.2_VISOR_PDF, "integración con asignaturas y
    # exámenes"): enlaza el examen/tarea a un documento concreto de la asignatura.
    documento_id = db.Column(db.Integer, db.ForeignKey("documento.id"), nullable=True)
    titulo = db.Column(db.String(200), nullable=False)
    fecha = db.Column(db.Date, nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False, default="tarea_general")
    completada = db.Column(db.Boolean, nullable=False, default=False)
    prioridad = db.Column(db.String(10), nullable=False, default="media")

    # Ampliación "Calendario académico" (spec punto 2): todos opcionales para no
    # romper tareas ya creadas sin estos datos.
    hora_inicio = db.Column(db.Time, nullable=True)
    hora_fin = db.Column(db.Time, nullable=True)
    aula = db.Column(db.String(100), nullable=True)
    ubicacion = db.Column(db.String(200), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    recordatorio = db.Column(db.Integer, nullable=True)  # días de aviso antes del evento
    link_relacionado = db.Column(db.String(500), nullable=True)

    asignatura = db.relationship("Asignatura")
    documento = db.relationship("Documento")

    @validates("tipo")
    def validar_tipo(self, key, value):
        if value not in TIPOS_TAREA:
            raise ValueError(f"tipo de Tarea/Evento debe ser uno de {TIPOS_TAREA}")
        return value

    @validates("prioridad")
    def validar_prioridad(self, key, value):
        if value not in PRIORIDADES_TAREA:
            raise ValueError(f"prioridad debe ser una de {PRIORIDADES_TAREA}")
        return value

    @validates("link_relacionado")
    def validar_link_relacionado(self, key, value):
        if value and not PATRON_URL.match(value.strip()):
            raise ValueError("link_relacionado debe ser una URL http(s) válida")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "asignatura_nombre": self.asignatura.nombre if self.asignatura else None,
            "asignatura_siglas": self.asignatura.siglas if self.asignatura else None,
            "documento_id": self.documento_id,
            "documento_nombre": self.documento.nombre_archivo if self.documento else None,
            "titulo": self.titulo,
            "fecha": self.fecha.isoformat(),
            "tipo": self.tipo,
            "completada": self.completada,
            "prioridad": self.prioridad,
            "hora_inicio": self.hora_inicio.strftime("%H:%M") if self.hora_inicio else None,
            "hora_fin": self.hora_fin.strftime("%H:%M") if self.hora_fin else None,
            "aula": self.aula,
            "ubicacion": self.ubicacion,
            "descripcion": self.descripcion,
            "recordatorio": self.recordatorio,
            "link_relacionado": self.link_relacionado,
        }


class EspacioEstudio(db.Model):
    """
    Espacio de Estudio: agrupa REFERENCIAS a Documento ya existentes (nunca copias
    ni movimientos) para preparar un examen/entrega/proyecto concreto. Nace siempre
    de una TareaEvento del calendario (relación 1:1); la fecha/asignatura/profesor
    se derivan de ella en vez de duplicarse aquí.
    """
    __tablename__ = "espacio_estudio"

    id = db.Column(db.Integer, primary_key=True)
    tarea_evento_id = db.Column(db.Integer, db.ForeignKey("tarea_evento.id"), nullable=False, unique=True)
    nombre = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # cascade en el backref: borrar el examen borra su Espacio de Estudio (y, por sus
    # propias relaciones cascade abajo, sus objetivos y referencias a documentos —
    # nunca los Documento reales, solo la fila de referencia).
    tarea_evento = db.relationship(
        "TareaEvento", backref=db.backref("espacio_estudio", uselist=False, cascade="all, delete-orphan")
    )
    documentos_ref = db.relationship(
        "EspacioEstudioDocumento", back_populates="espacio",
        cascade="all, delete-orphan", order_by="EspacioEstudioDocumento.orden",
    )
    objetivos = db.relationship(
        "ObjetivoEspacio", back_populates="espacio",
        cascade="all, delete-orphan", order_by="ObjetivoEspacio.orden",
    )

    @validates("nombre")
    def validar_nombre(self, key, value):
        limpio = re.sub(r"\s+", " ", (value or "")).strip()
        if not limpio:
            raise ValueError("nombre de EspacioEstudio no puede estar vacío")
        return limpio

    def to_dict(self, include_detalle=False):
        asignatura = self.tarea_evento.asignatura if self.tarea_evento else None
        total = len(self.documentos_ref)
        leidos = sum(1 for ref in self.documentos_ref if ref.leido)
        data = {
            "id": self.id,
            "tarea_evento_id": self.tarea_evento_id,
            "nombre": self.nombre,
            "fecha": self.tarea_evento.fecha.isoformat() if self.tarea_evento else None,
            "dias_restantes": (self.tarea_evento.fecha - date.today()).days if self.tarea_evento else None,
            # Para "Modo examen" (pantalla del día del examen, sin ir a buscarlo al
            # calendario): mismos datos que TareaEvento.to_dict(), leídos de la
            # relación ya cargada, sin otra consulta.
            "hora_inicio": self.tarea_evento.hora_inicio.strftime("%H:%M") if self.tarea_evento and self.tarea_evento.hora_inicio else None,
            "hora_fin": self.tarea_evento.hora_fin.strftime("%H:%M") if self.tarea_evento and self.tarea_evento.hora_fin else None,
            "aula": self.tarea_evento.aula if self.tarea_evento else None,
            "ubicacion": self.tarea_evento.ubicacion if self.tarea_evento else None,
            "asignatura_id": asignatura.id if asignatura else None,
            "asignatura_nombre": asignatura.nombre if asignatura else None,
            "asignatura_siglas": asignatura.siglas if asignatura else None,
            "profesores": [p.nombre for p in asignatura.profesores] if asignatura else [],
            "total_documentos": total,
            "documentos_leidos": leidos,
            "documentos_pendientes": total - leidos,
            "progreso_pct": round((leidos / total) * 100) if total else 0,
            "total_objetivos": len(self.objetivos),
            "objetivos_completados": sum(1 for o in self.objetivos if o.completada),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_detalle:
            data["documentos_ref"] = [d.to_dict() for d in self.documentos_ref]
            data["objetivos"] = [o.to_dict() for o in self.objetivos]
        return data


class EspacioEstudioDocumento(db.Model):
    """
    Referencia (no copia) de un Documento dentro de un Espacio de Estudio, con
    metadatos propios de esa asociación: sección donde se muestra, si ya se ha
    leído para ESTE espacio (distinto de Documento.porcentaje_leido, que es la
    posición de scroll del visor PDF, global al documento) y si está destacado
    como material importante. Un documento solo puede referenciarse una vez por
    espacio (cambiar de sección es un PUT sobre esta misma fila).
    """
    __tablename__ = "espacio_estudio_documento"
    __table_args__ = (
        db.UniqueConstraint("espacio_estudio_id", "documento_id", name="uq_espacio_documento"),
    )

    id = db.Column(db.Integer, primary_key=True)
    espacio_estudio_id = db.Column(db.Integer, db.ForeignKey("espacio_estudio.id"), nullable=False)
    documento_id = db.Column(db.Integer, db.ForeignKey("documento.id"), nullable=False)
    seccion = db.Column(db.String(30), nullable=False)
    leido = db.Column(db.Boolean, nullable=False, default=False)
    destacado = db.Column(db.Boolean, nullable=False, default=False)
    orden = db.Column(db.Integer, nullable=False, default=0)
    fecha_referencia = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    espacio = db.relationship("EspacioEstudio", back_populates="documentos_ref")
    documento = db.relationship("Documento", back_populates="referencias_espacio_estudio")

    @validates("seccion")
    def validar_seccion(self, key, value):
        if value not in SECCIONES_ESPACIO_ESTUDIO:
            raise ValueError(f"seccion debe ser una de {SECCIONES_ESPACIO_ESTUDIO}")
        return value

    def to_dict(self):
        asignatura = self.documento.asignatura if self.documento else None
        return {
            "id": self.id,
            "espacio_estudio_id": self.espacio_estudio_id,
            "documento_id": self.documento_id,
            "documento": self.documento.to_dict() if self.documento else None,
            "documento_asignatura_nombre": asignatura.nombre if asignatura else None,
            "documento_asignatura_siglas": asignatura.siglas if asignatura else None,
            "seccion": self.seccion,
            "leido": self.leido,
            "destacado": self.destacado,
            "orden": self.orden,
            "fecha_referencia": self.fecha_referencia.isoformat(),
        }


class ObjetivoEspacio(db.Model):
    """Ítem de la checklist "✅ Tareas" de un Espacio de Estudio (p. ej. "Leer Tema 4").
    Nombre deliberadamente distinto de "tarea" para no chocar con TareaEvento, que ya
    significa "tarea/evento del calendario" en esta base de código."""
    __tablename__ = "objetivo_espacio"

    id = db.Column(db.Integer, primary_key=True)
    espacio_estudio_id = db.Column(db.Integer, db.ForeignKey("espacio_estudio.id"), nullable=False)
    texto = db.Column(db.String(300), nullable=False)
    completada = db.Column(db.Boolean, nullable=False, default=False)
    orden = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    espacio = db.relationship("EspacioEstudio", back_populates="objetivos")

    @validates("texto")
    def validar_texto(self, key, value):
        limpio = (value or "").strip()
        if not limpio:
            raise ValueError("texto de ObjetivoEspacio no puede estar vacío")
        return limpio

    def to_dict(self):
        return {
            "id": self.id,
            "espacio_estudio_id": self.espacio_estudio_id,
            "texto": self.texto,
            "completada": self.completada,
            "orden": self.orden,
            "created_at": self.created_at.isoformat(),
        }


class HorarioClase(db.Model):
    """
    Serie recurrente de clase/laboratorio (spec Fase Calendario/Horario punto 4):
    UNA fila representa toda la serie (p. ej. "DSED Laboratorio los martes de
    15:00 a 17:00 del 8/9 al 20/12, cada semana"), no una fila por sesión. Las
    fechas concretas de cada sesión se calculan bajo demanda con
    `fechas_sesiones_horario()`, no se guardan copias — así editar o borrar la
    serie es una sola operación sobre una sola fila.

    Deliberadamente sin entidad de excepciones (spec punto 6): editar o borrar
    afecta a toda la serie, no a una sesión suelta.
    """
    __tablename__ = "horario_clase"

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False)  # 1=lunes ... 5=viernes
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    aula = db.Column(db.String(100), nullable=True)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    intervalo_semanas = db.Column(db.Integer, nullable=False, default=1)
    notas = db.Column(db.Text, nullable=True)

    asignatura = db.relationship("Asignatura")

    @validates("tipo")
    def validar_tipo(self, key, value):
        if value not in TIPOS_HORARIO:
            raise ValueError(f"tipo de HorarioClase debe ser uno de {TIPOS_HORARIO}")
        return value

    @validates("dia_semana")
    def validar_dia_semana(self, key, value):
        if value not in DIAS_SEMANA:
            raise ValueError(f"dia_semana debe ser uno de {DIAS_SEMANA} (1=lunes...5=viernes)")
        return value

    @validates("intervalo_semanas")
    def validar_intervalo_semanas(self, key, value):
        if value not in INTERVALOS_SEMANAS:
            raise ValueError(f"intervalo_semanas debe ser uno de {INTERVALOS_SEMANAS}")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "asignatura_nombre": self.asignatura.nombre if self.asignatura else None,
            "asignatura_siglas": self.asignatura.siglas if self.asignatura else None,
            "tipo": self.tipo,
            "dia_semana": self.dia_semana,
            "hora_inicio": self.hora_inicio.strftime("%H:%M"),
            "hora_fin": self.hora_fin.strftime("%H:%M"),
            "aula": self.aula,
            "fecha_inicio": self.fecha_inicio.isoformat(),
            "fecha_fin": self.fecha_fin.isoformat(),
            "intervalo_semanas": self.intervalo_semanas,
            "notas": self.notas,
        }


def fechas_sesiones_horario(horario):
    """
    Genera la lista de fechas (date) de cada sesión de una serie HorarioClase,
    entre fecha_inicio y fecha_fin inclusive, respetando el día de la semana y el
    intervalo (spec punto 4: "la primera sesión calculada dentro del intervalo
    marca el inicio del patrón de cada dos semanas" — es decir, la propia
    fecha_inicio no tiene por qué caer en el día de la semana elegido; se busca la
    primera ocurrencia de ese día a partir de fecha_inicio y esa es la semana 0
    del patrón quincenal).
    """
    dias_hasta_el_primero = (horario.dia_semana - 1 - horario.fecha_inicio.weekday()) % 7
    primera_sesion = horario.fecha_inicio + timedelta(days=dias_hasta_el_primero)

    paso = timedelta(weeks=horario.intervalo_semanas)
    fechas = []
    actual = primera_sesion
    while actual <= horario.fecha_fin:
        if actual >= horario.fecha_inicio:
            fechas.append(actual)
        actual += paso
    return fechas


def intervalos_solapan(inicio1, fin1, inicio2, fin2):
    """True si dos intervalos [inicio, fin) de horas se cruzan en algún punto."""
    return inicio1 < fin2 and inicio2 < fin1


def fecha_es_sesion_de_horario(fecha, horario):
    """
    Igual que comprobar si `fecha` está en `fechas_sesiones_horario(horario)`, pero
    sin generar la lista completa: para detección de conflictos se comprueba una
    fecha suelta muchas veces, así que conviene que sea O(1).
    """
    if not (horario.fecha_inicio <= fecha <= horario.fecha_fin):
        return False
    if fecha.isoweekday() != horario.dia_semana:
        return False
    dias_hasta_el_primero = (horario.dia_semana - 1 - horario.fecha_inicio.weekday()) % 7
    primera_sesion = horario.fecha_inicio + timedelta(days=dias_hasta_el_primero)
    diferencia_dias = (fecha - primera_sesion).days
    if diferencia_dias < 0:
        return False
    return diferencia_dias % (7 * horario.intervalo_semanas) == 0


TEMAS = ("claro", "oscuro")


class ConfiguracionApp(db.Model):
    """Fila única (id=1) con las preferencias/ajustes globales de la app."""
    __tablename__ = "configuracion_app"

    id = db.Column(db.Integer, primary_key=True)
    tema = db.Column(db.String(10), nullable=False, default="oscuro")
    dias_aviso_examen = db.Column(db.Integer, nullable=False, default=7)
    dias_asignatura_abandonada = db.Column(db.Integer, nullable=False, default=14)
    widgets_orden = db.Column(db.String(200), nullable=False, default=",".join(WIDGETS_POR_DEFECTO))
    widgets_ocultos = db.Column(db.String(200), nullable=True)
    objetivo_media = db.Column(db.Float, nullable=True)  # nota media que quiere sacar el usuario (0-10)

    @validates("objetivo_media")
    def validar_objetivo_media(self, key, value):
        if value is not None and not (0 <= float(value) <= 10):
            raise ValueError("objetivo_media debe estar entre 0 y 10")
        return value

    @validates("tema")
    def validar_tema(self, key, value):
        if value not in TEMAS:
            raise ValueError(f"tema debe ser uno de {TEMAS}")
        return value

    @validates("dias_aviso_examen", "dias_asignatura_abandonada")
    def validar_dias(self, key, value):
        if value is None or int(value) < 1:
            raise ValueError(f"{key} debe ser un número de días mayor o igual que 1")
        return value

    def lista_widgets_orden(self):
        if not self.widgets_orden:
            return list(WIDGETS_POR_DEFECTO)
        return [w.strip() for w in self.widgets_orden.split(",") if w.strip()]

    def lista_widgets_ocultos(self):
        if not self.widgets_ocultos:
            return []
        return [w.strip() for w in self.widgets_ocultos.split(",") if w.strip()]

    def to_dict(self):
        return {
            "id": self.id,
            "tema": self.tema,
            "dias_aviso_examen": self.dias_aviso_examen,
            "dias_asignatura_abandonada": self.dias_asignatura_abandonada,
            "widgets_orden": self.lista_widgets_orden(),
            "widgets_ocultos": self.lista_widgets_ocultos(),
            "objetivo_media": self.objetivo_media,
        }


class Hito(db.Model):
    """Certificaciones y proyectos propios (spec punto 8), hitos libres editables por el usuario."""
    __tablename__ = "hito"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="pendiente")
    fecha = db.Column(db.Date, nullable=True)
    orden = db.Column(db.Integer, nullable=False, default=0)

    @validates("estado")
    def validar_estado(self, key, value):
        if value not in ESTADOS_HITO:
            raise ValueError(f"estado de Hito debe ser uno de {ESTADOS_HITO}")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "estado": self.estado,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "orden": self.orden,
        }


class Concepto(db.Model):
    """Concepto/tema dentro de una asignatura, con repetición espaciada simplificada (spec punto 7)."""
    __tablename__ = "concepto"

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="no_visto")
    ultima_revision = db.Column(db.Date, nullable=True)
    proxima_revision = db.Column(db.Date, nullable=False, default=date.today, index=True)

    asignatura = db.relationship("Asignatura", back_populates="conceptos")

    @validates("estado")
    def validar_estado(self, key, value):
        if value not in ORDEN_ESTADOS_CONCEPTO:
            raise ValueError(f"estado de Concepto debe ser uno de {ORDEN_ESTADOS_CONCEPTO}")
        return value

    def reclasificar(self, direccion):
        """direccion: +1 para subir de nivel (mejor dominio), -1 para bajar."""
        indice = ORDEN_ESTADOS_CONCEPTO.index(self.estado)
        nuevo_indice = max(0, min(len(ORDEN_ESTADOS_CONCEPTO) - 1, indice + direccion))
        self.estado = ORDEN_ESTADOS_CONCEPTO[nuevo_indice]
        self.ultima_revision = date.today()
        self.proxima_revision = date.today() + timedelta(days=INTERVALO_DIAS_CONCEPTO[self.estado])

    def to_dict(self):
        return {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "asignatura_nombre": self.asignatura.nombre if self.asignatura else None,
            "nombre": self.nombre,
            "estado": self.estado,
            "ultima_revision": self.ultima_revision.isoformat() if self.ultima_revision else None,
            "proxima_revision": self.proxima_revision.isoformat(),
        }


class PaginaTexto(db.Model):
    """Texto extraído de cada página de un PDF, para poder buscar por contenido (spec punto 20)."""
    __tablename__ = "pagina_texto"

    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey("documento.id"), nullable=False, index=True)
    numero_pagina = db.Column(db.Integer, nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    # Versión de `contenido` ya normalizada (sin acentos, en minúsculas), calculada una
    # sola vez al indexar en vez de en cada búsqueda: con miles de páginas indexadas,
    # renormalizar todo el texto en cada petición de /buscar era el cuello de botella
    # real (~1s en un catálogo de tamaño medio). Mismo índice de caracteres que
    # `contenido` (la normalización NFKD + descarte de combinantes conserva la
    # posición de cada carácter base), así _fragmento() sigue pudiendo recortar el
    # contenido original con el índice hallado en la versión normalizada.
    contenido_normalizado = db.Column(db.Text, nullable=True)

    documento = db.relationship("Documento", back_populates="paginas_texto")

    def to_dict(self):
        return {
            "id": self.id,
            "documento_id": self.documento_id,
            "numero_pagina": self.numero_pagina,
        }


class AvisoDescartado(db.Model):
    """Un aviso de calcular_notificaciones() (routes/notificaciones.py) descartado
    por el usuario para hoy: vuelve a aparecer mañana si sigue siendo cierto, en vez
    de exigir completar la tarea/leer el espacio de verdad solo para quitarlo de la
    campanita. (tipo, entidad_id) identifica el aviso igual que lo hace el frontend."""
    __tablename__ = "aviso_descartado"

    tipo = db.Column(db.String(30), primary_key=True)
    entidad_id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, primary_key=True)


class DiaActividad(db.Model):
    """Un día en el que hubo actividad real de estudio (leer un documento, completar
    una tarea, revisar un concepto): una fila por día, para calcular la racha (días
    consecutivos) sin reconstruirla a partir de fecha_ultima_apertura de Documento
    (que solo guarda la ÚLTIMA apertura de CADA documento, no un histórico de días)."""
    __tablename__ = "dia_actividad"

    fecha = db.Column(db.Date, primary_key=True)


def registrar_actividad_hoy():
    """Llamar desde cualquier acción que cuente como "estudiar hoy" (spec racha de
    estudio). Idempotente: como máximo una fila por día, sin importar cuántas veces
    se llame. No hace commit propio: se guarda junto al commit de quien la llama."""
    hoy = date.today()
    if db.session.get(DiaActividad, hoy) is None:
        db.session.add(DiaActividad(fecha=hoy))


def calcular_racha_actual():
    """Días consecutivos de actividad terminando hoy o ayer (si hoy aún no hay
    actividad registrada, la racha de ayer sigue "viva" hasta que acabe el día)."""
    dias = {d.fecha for d in DiaActividad.query.all()}
    hoy = date.today()
    cursor = hoy if hoy in dias else hoy - timedelta(days=1)
    racha = 0
    while cursor in dias:
        racha += 1
        cursor -= timedelta(days=1)
    return racha


def calcular_racha_maxima():
    """Racha más larga de toda la historia (no solo la que sigue viva ahora mismo)."""
    dias = sorted(d.fecha for d in DiaActividad.query.all())
    mejor = racha = 0
    anterior = None
    for fecha in dias:
        racha = racha + 1 if anterior == fecha - timedelta(days=1) else 1
        mejor = max(mejor, racha)
        anterior = fecha
    return mejor


class RecursoExterno(db.Model):
    """
    Enlaces externos libres de una asignatura (Wuolah, Studocu, Drive, GitHub, etc.).

    Se modela como entidad relacionada 1:N en vez de un campo JSON porque el resto del
    proyecto ya sigue ese patrón de forma consistente para toda relación "una asignatura
    tiene varios X" (Documento, Marcador, Concepto, ComponenteEvaluacion...), lo que da
    CRUD, orden y validación por fila igual que las demás entidades, sin introducir un
    mecanismo de almacenamiento distinto solo para este caso.
    """
    __tablename__ = "recurso_externo"

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    tipo = db.Column(db.String(50), nullable=True)  # valor libre (p. ej. "apuntes", "repositorio")
    orden = db.Column(db.Integer, nullable=False, default=0)

    asignatura = db.relationship("Asignatura", back_populates="recursos_externos")

    @validates("url")
    def validar_url(self, key, value):
        if not value or not PATRON_URL.match(value.strip()):
            raise ValueError("url de RecursoExterno debe ser una URL http(s) válida")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "nombre": self.nombre,
            "url": self.url,
            "tipo": self.tipo,
            "orden": self.orden,
        }


class Profesor(db.Model):
    """
    Profesorado de una asignatura (1:N): a diferencia de nombre_profesor/correo_profesor/
    despacho_profesor/link_aula_virtual de Asignatura (un único profesor "de contacto",
    conservados por compatibilidad con datos ya existentes), esta entidad permite que una
    asignatura tenga varios profesores (p. ej. uno de teoría y otro de laboratorio).
    """
    __tablename__ = "profesor"

    id = db.Column(db.Integer, primary_key=True)
    asignatura_id = db.Column(db.Integer, db.ForeignKey("asignatura.id"), nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(100), nullable=True)  # texto libre: "Responsable", "Grupos 11, 12", "Laboratorio"...
    correo = db.Column(db.String(200), nullable=True)
    despacho = db.Column(db.String(200), nullable=True)
    aula_virtual = db.Column(db.String(500), nullable=True)
    orden = db.Column(db.Integer, nullable=False, default=0)

    asignatura = db.relationship("Asignatura", back_populates="profesores")

    @validates("correo")
    def validar_correo(self, key, value):
        if value and not PATRON_EMAIL.match(value.strip()):
            raise ValueError("correo de Profesor no tiene un formato de email válido")
        return value

    @validates("aula_virtual")
    def validar_aula_virtual(self, key, value):
        if value and not PATRON_URL.match(value.strip()):
            raise ValueError("aula_virtual de Profesor debe ser una URL http(s) válida")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "asignatura_id": self.asignatura_id,
            "nombre": self.nombre,
            "rol": self.rol,
            "correo": self.correo,
            "despacho": self.despacho,
            "aula_virtual": self.aula_virtual,
            "orden": self.orden,
        }


class BusquedaFavorito(db.Model):
    """Favorito del buscador global (V2.1): referencia genérica a cualquier entidad
    indexada (asignatura, documento, tarea...), identificada por tipo_entidad+entidad_id
    en vez de una FK real, ya que puede apuntar a distintas tablas."""
    __tablename__ = "busqueda_favorito"
    __table_args__ = (db.UniqueConstraint("tipo_entidad", "entidad_id", name="uq_favorito_entidad"),)

    id = db.Column(db.Integer, primary_key=True)
    tipo_entidad = db.Column(db.String(20), nullable=False)
    entidad_id = db.Column(db.Integer, nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @validates("tipo_entidad")
    def validar_tipo_entidad(self, key, value):
        if value not in TIPOS_ENTIDAD_BUSQUEDA:
            raise ValueError(f"tipo_entidad debe ser uno de {TIPOS_ENTIDAD_BUSQUEDA}")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "tipo_entidad": self.tipo_entidad,
            "entidad_id": self.entidad_id,
            "fecha_creacion": self.fecha_creacion.isoformat(),
        }


class BusquedaReciente(db.Model):
    """Historial de resultados del buscador global abiertos recientemente. Se recorta
    a un máximo por escritura (ver routes/busqueda.py) en vez de acumular sin límite."""
    __tablename__ = "busqueda_reciente"

    id = db.Column(db.Integer, primary_key=True)
    tipo_entidad = db.Column(db.String(20), nullable=False)
    entidad_id = db.Column(db.Integer, nullable=False)
    etiqueta_mostrada = db.Column(db.String(300), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    fecha_acceso = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @validates("tipo_entidad")
    def validar_tipo_entidad(self, key, value):
        if value not in TIPOS_ENTIDAD_BUSQUEDA:
            raise ValueError(f"tipo_entidad debe ser uno de {TIPOS_ENTIDAD_BUSQUEDA}")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "tipo_entidad": self.tipo_entidad,
            "entidad_id": self.entidad_id,
            "etiqueta_mostrada": self.etiqueta_mostrada,
            "url": self.url,
            "fecha_acceso": self.fecha_acceso.isoformat(),
        }


class NotaRapida(db.Model):
    """Apunte suelto para anotar algo al vuelo mientras se estudia, sin perder de
    vista lo que se está mirando (panel accesible desde cualquier página, igual que
    la campanita/buscador). Deliberadamente sin asignatura ni ningún otro vínculo:
    es un bloc de notas, no una entidad más del modelo académico."""
    __tablename__ = "nota_rapida"

    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.String(1000), nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @validates("texto")
    def validar_texto(self, key, value):
        limpio = (value or "").strip()
        if not limpio:
            raise ValueError("texto de NotaRapida no puede estar vacío")
        return limpio

    def to_dict(self):
        return {
            "id": self.id,
            "texto": self.texto,
            "fecha_creacion": self.fecha_creacion.isoformat(),
        }
