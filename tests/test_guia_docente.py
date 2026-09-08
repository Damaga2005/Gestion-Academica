"""
Tests de la extracción heurística de guías docentes (guia_docente.py) y de las
rutas de análisis/importación (routes/guia_docente.py): nunca debe escribirse
nada en la base de datos sin pasar por /importar-guia-docente, y nunca debe
inventarse un porcentaje que no se pueda determinar con confianza.
"""
import io

import pytest

import guia_docente as gd


# --- Heurística: profesorado ---

def test_profesorado_responsable_y_otros():
    texto = """
PROFESORADO
Profesorado responsable: EVA RODRIGUEZ LUNA
Otros: Primer quadrimestre:
JUAN CARLOS CRUELLAS IBARZ - 11
EVA RODRIGUEZ LUNA - 11, 12, 13
CAPACIDADES PREVIAS
Resolución de sistemas lineales.
"""
    profesores = gd.analizar_profesorado(texto)
    assert profesores == [
        {"nombre": "EVA RODRIGUEZ LUNA", "rol": "Responsable (grupos 11, 12, 13)"},
        {"nombre": "JUAN CARLOS CRUELLAS IBARZ", "rol": "Grupo 11"},
    ]


def test_profesorado_sin_publicar_no_inventa_nombre():
    texto = """
PROFESORADO
Profesorado responsable:
Otros:
CAPACIDADES PREVIAS
"""
    assert gd.analizar_profesorado(texto) == []


def test_profesorado_sin_seccion():
    assert gd.analizar_profesorado("CONTENIDOS\nTema 1\n") == []


# --- Heurística: evaluación, caso A (lista plana con %) ---

def test_evaluacion_lista_plana_alta_confianza():
    texto = """
SISTEMA DE CALIFICACIÓN
Nota de laboratorio (LAB): 10%
Problemas y actividades a casa (PRO): 10%
Examen parcial de teoría durante el curso (EXPAR): 30%
Examen final de teoría (EXFIN): 50%
BIBLIOGRAFÍA
"""
    esquemas = gd.analizar_evaluacion(texto)
    assert len(esquemas) == 1
    esquema = esquemas[0]
    assert esquema["pendiente_revision"] is False
    assert len(esquema["componentes"]) == 4
    assert sum(c["porcentaje"] for c in esquema["componentes"]) == 100
    assert all(not c["pendiente_revision"] for c in esquema["componentes"])


def test_evaluacion_linea_sin_dos_puntos_tambien_vale():
    """Caso PPE real: una de las líneas no lleva ':' antes del %."""
    texto = """
SISTEMA DE CALIFICACIÓN
Qüestionaris quinzenals 10%
Exámenes parciales: 40%
Examen final: 50%
BIBLIOGRAFÍA
"""
    esquemas = gd.analizar_evaluacion(texto)
    assert len(esquemas) == 1
    assert len(esquemas[0]["componentes"]) == 3
    assert sum(c["porcentaje"] for c in esquemas[0]["componentes"]) == 100


def test_evaluacion_fragmento_de_frase_partido_no_cuela():
    """Regresión: un salto de línea de PDF puede dejar un trozo de frase larga que
    termina justo en '... NN%.' (p. ej. 'evaluación anterior con un peso del 10%.').
    El límite de 5 palabras en las líneas sin ':' debe descartar ese fragmento
    (es una frase, no una etiqueta corta), dejando solo los 4 componentes reales;
    si por lo que sea colase igual, la suma dejaría de ser 100 y se descartaría
    la lista plana entera en vez de proponer un desglose con un % de más."""
    texto = """
SISTEMA DE CALIFICACIÓN
Nota de laboratorio (LAB): 10%
Problemas y actividades a casa (PRO): 10%
Examen parcial de teoría durante el curso (EXPAR): 30%
Examen final de teoría (EXFIN): 50%
Solamente es reevaluable la parte de teoría con un peso del 90%. La nota de laboratorio se conservará de la
evaluación anterior con un peso del 10%.
BIBLIOGRAFÍA
"""
    esquemas = gd.analizar_evaluacion(texto)
    assert len(esquemas) == 1
    assert esquemas[0]["pendiente_revision"] is False
    assert len(esquemas[0]["componentes"]) == 4
    assert sum(c["porcentaje"] for c in esquemas[0]["componentes"]) == 100


# --- Heurística: evaluación, caso B (fórmula MAX con sustitución) ---

def test_evaluacion_formula_max_con_sustitucion():
    texto = """
SISTEMA DE CALIFICACIÓN
Nota final = MAX (0.6*Examen_final, 0.4*Examen_final + 0.2*Examen_parcial) + 0.4*Nota_laboratorio
Nota_laboratorio = 0.5*Examen_lab + 0.5*Proyecto
BIBLIOGRAFÍA
"""
    esquemas = gd.analizar_evaluacion(texto)
    assert len(esquemas) == 2
    por_nombre = {e["nombre"]: e for e in esquemas}
    assert set(por_nombre) == {"Con examen parcial", "Solo examen final"}

    solo_final = por_nombre["Solo examen final"]
    pesos = {c["nombre"]: c["porcentaje"] for c in solo_final["componentes"]}
    assert pesos["Examen final"] == 60
    assert pesos["Examen lab"] == 20
    assert pesos["Proyecto"] == 20
    assert all(c["pendiente_revision"] for c in solo_final["componentes"])

    con_parcial = por_nombre["Con examen parcial"]
    pesos2 = {c["nombre"]: c["porcentaje"] for c in con_parcial["componentes"]}
    assert pesos2["Examen final"] == 40
    assert pesos2["Examen parcial"] == 20
    assert pesos2["Examen lab"] == 20
    assert pesos2["Proyecto"] == 20


def test_evaluacion_rubrica_sin_porcentajes_queda_pendiente():
    texto = """
SISTEMA DE CALIFICACIÓN
Se asigna una nota global al proyecto desarrollado por el equipo utilizando una rúbrica
que tiene en cuenta los diferentes aspectos del proceso.
BIBLIOGRAFÍA
"""
    esquemas = gd.analizar_evaluacion(texto)
    assert len(esquemas) == 1
    assert esquemas[0]["pendiente_revision"] is True
    assert esquemas[0]["componentes"] == []
    assert "rúbrica" in esquemas[0]["texto_sin_analizar"]


def test_evaluacion_sin_seccion():
    assert gd.analizar_evaluacion("CONTENIDOS\nTema 1\n") == []


# --- Rutas: analizar (solo lectura) e importar (con modo añadir/reemplazar) ---

@pytest.fixture
def asignatura_id(client_abierto):
    return client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]


@pytest.fixture
def documento_pdf(client_abierto, asignatura_id):
    data = {"archivos": (io.BytesIO(b"%PDF-1.4 contenido falso"), "guia.pdf")}
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/teoria/documentos",
        data=data, content_type="multipart/form-data",
    )
    assert r.status_code == 201
    return r.get_json()[0]["id"]


def test_analizar_no_escribe_nada_en_bd(client_abierto, asignatura_id, documento_pdf, monkeypatch):
    monkeypatch.setattr(
        "routes.guia_docente.extraer_texto",
        lambda ruta: "PROFESORADO\nProfesorado responsable: ANA GARCIA\nOtros:\nCAPACIDADES PREVIAS",
    )
    r = client_abierto.post(f"/documentos/{documento_pdf}/analizar-guia-docente")
    assert r.status_code == 200
    data = r.get_json()
    assert data["profesores"] == [{"nombre": "ANA GARCIA", "rol": None}]
    assert data["asignatura_tiene_profesores"] is False

    # No debe haberse creado ningún profesor de verdad todavía
    profesores = client_abierto.get(f"/asignaturas/{asignatura_id}/profesores").get_json()
    assert profesores == []


def test_analizar_rechaza_documento_no_pdf(client_abierto, asignatura_id):
    data = {"archivos": (io.BytesIO(b"contenido"), "notas.txt")}
    r = client_abierto.post(
        f"/asignaturas/{asignatura_id}/categorias/otros/documentos",
        data=data, content_type="multipart/form-data",
    )
    documento_id = r.get_json()[0]["id"]
    r2 = client_abierto.post(f"/documentos/{documento_id}/analizar-guia-docente")
    assert r2.status_code == 400


def test_importar_crea_profesores_y_esquemas(client_abierto, asignatura_id):
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/importar-guia-docente", json={
        "profesores": [{"nombre": "Ana García", "rol": "Responsable"}],
        "esquemas": [{"nombre": "Evaluación", "componentes": [
            {"nombre": "Examen final", "tipo": "examen_final", "porcentaje": 100},
        ]}],
    })
    assert r.status_code == 200
    profesores = client_abierto.get(f"/asignaturas/{asignatura_id}/profesores").get_json()
    assert len(profesores) == 1
    assert profesores[0]["nombre"] == "Ana García"
    esquemas = client_abierto.get(f"/asignaturas/{asignatura_id}/esquemas").get_json()
    assert len(esquemas) == 1
    assert esquemas[0]["componentes"][0]["porcentaje"] == 100


def test_importar_modo_anadir_no_borra_lo_existente(client_abierto, asignatura_id):
    client_abierto.post(f"/asignaturas/{asignatura_id}/profesores", json={"nombre": "Profesor Previo"})
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/importar-guia-docente", json={
        "profesores": [{"nombre": "Profesor Nuevo"}],
        "modo_profesores": "añadir",
    })
    assert r.status_code == 200
    nombres = {p["nombre"] for p in client_abierto.get(f"/asignaturas/{asignatura_id}/profesores").get_json()}
    assert nombres == {"Profesor Previo", "Profesor Nuevo"}


def test_importar_modo_reemplazar_borra_lo_existente(client_abierto, asignatura_id):
    client_abierto.post(f"/asignaturas/{asignatura_id}/profesores", json={"nombre": "Profesor Previo"})
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/importar-guia-docente", json={
        "profesores": [{"nombre": "Profesor Nuevo"}],
        "modo_profesores": "reemplazar",
    })
    assert r.status_code == 200
    nombres = {p["nombre"] for p in client_abierto.get(f"/asignaturas/{asignatura_id}/profesores").get_json()}
    assert nombres == {"Profesor Nuevo"}


def test_importar_modo_reemplazar_esquemas_no_deja_componentes_huerfanos(app_abierta, client_abierto, asignatura_id):
    client_abierto.post(f"/asignaturas/{asignatura_id}/importar-guia-docente", json={
        "esquemas": [{"nombre": "Evaluación previa", "componentes": [
            {"nombre": "Parcial", "tipo": "examen_parcial", "porcentaje": 100},
        ]}],
    })
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/importar-guia-docente", json={
        "esquemas": [{"nombre": "Evaluación nueva", "componentes": [
            {"nombre": "Final", "tipo": "examen_final", "porcentaje": 100},
        ]}],
        "modo_esquemas": "reemplazar",
    })
    assert r.status_code == 200

    with app_abierta.app_context():
        from models import ComponenteEvaluacion
        componentes = ComponenteEvaluacion.query.filter_by(asignatura_id=asignatura_id).all()
        assert len(componentes) == 1
        assert componentes[0].nombre == "Final"


def test_importar_modo_invalido_rechazado(client_abierto, asignatura_id):
    client_abierto.post(f"/asignaturas/{asignatura_id}/profesores", json={"nombre": "Profesor Previo"})
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/importar-guia-docente", json={
        "profesores": [{"nombre": "Profesor Nuevo"}],
        "modo_profesores": "lo-que-sea",
    })
    assert r.status_code == 400


def test_importar_componente_sin_porcentaje_rechazado(client_abierto, asignatura_id):
    r = client_abierto.post(f"/asignaturas/{asignatura_id}/importar-guia-docente", json={
        "esquemas": [{"nombre": "Evaluación", "componentes": [
            {"nombre": "Examen final", "tipo": "examen_final"},
        ]}],
    })
    assert r.status_code == 400
    # No debe quedar ningún esquema a medio crear
    assert client_abierto.get(f"/asignaturas/{asignatura_id}/esquemas").get_json() == []
