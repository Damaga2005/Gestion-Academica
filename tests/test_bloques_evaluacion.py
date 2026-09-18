"""
Bloques de evaluación (nota jerárquica, models.py BloqueEvaluacion): un grupo de
componentes cuya propia nota se calcula a partir de ellos (p. ej. Laboratorio 40%
de la nota final, calculado a su vez a partir de prácticas/controles). Sin bloques,
el esquema se comporta exactamente igual que antes.
"""

import pytest


@pytest.fixture
def cuatrimestre_id(client_abierto):
    anio = client_abierto.get("/anios").get_json()[0]
    detalle = client_abierto.get(f"/anios/{anio['id']}").get_json()
    return detalle["cuatrimestres"][0]["id"]


@pytest.fixture
def asignatura_id(client_abierto, cuatrimestre_id):
    return client_abierto.post("/asignaturas", json={
        "cuatrimestre_id": cuatrimestre_id, "nombre": "Diseño Digital", "creditos_ects": 6,
    }).get_json()["id"]


@pytest.fixture
def esquema_id(client_abierto, asignatura_id):
    return client_abierto.post(f"/asignaturas/{asignatura_id}/esquemas", json={"nombre": "Evaluación"}).get_json()["id"]


def _crear_bloque(client, esquema_id, nombre, porcentaje):
    r = client.post(f"/esquemas/{esquema_id}/bloques", json={"nombre": nombre, "porcentaje": porcentaje})
    assert r.status_code == 201
    return r.get_json()["id"]


def _crear_componente_bloque(client, bloque_id, porcentaje, nota=None):
    r = client.post(f"/bloques/{bloque_id}/componentes", json={
        "nombre": "Sub", "porcentaje": porcentaje, "nota": nota,
    })
    assert r.status_code == 201
    return r.get_json()["id"]


def _crear_componente_suelto(client, esquema_id, porcentaje, nota=None):
    r = client.post(f"/esquemas/{esquema_id}/componentes", json={
        "nombre": "Suelto", "porcentaje": porcentaje, "nota": nota,
    })
    assert r.status_code == 201
    return r.get_json()["id"]


def _esquema(client, asignatura_id):
    return client.get(f"/asignaturas/{asignatura_id}/esquemas").get_json()[0]


# --- Sin bloques: comportamiento sin cambios ---

def test_esquema_sin_bloques_no_cambia(client_abierto, esquema_id, asignatura_id):
    _crear_componente_suelto(client_abierto, esquema_id, 100, nota=8)
    esquema = _esquema(client_abierto, asignatura_id)
    assert esquema["bloques"] == []
    assert esquema["resultado"]["media_ponderada"] == 8


# --- Cálculo jerárquico ---

def test_bloque_calcula_su_propia_nota_y_pesa_en_el_esquema(client_abierto, esquema_id, asignatura_id):
    # Teoría suelta 60%, con nota 8.
    _crear_componente_suelto(client_abierto, esquema_id, 60, nota=8)
    # Laboratorio 40%, con dos sub-componentes: 50%+50%, notas 6 y 10 -> media 8.
    bloque_id = _crear_bloque(client_abierto, esquema_id, "Laboratorio", 40)
    _crear_componente_bloque(client_abierto, bloque_id, 50, nota=6)
    _crear_componente_bloque(client_abierto, bloque_id, 50, nota=10)

    esquema = _esquema(client_abierto, asignatura_id)
    assert esquema["bloques"][0]["resultado"]["media_ponderada"] == 8
    # Nota final = 8*0.6 + 8*0.4 = 8 (mismo valor por coincidencia, pero calculado
    # de verdad combinando ambos pesos, no solo copiado).
    assert esquema["resultado"]["media_ponderada"] == 8


def test_bloque_con_notas_distintas_pesa_correctamente(client_abierto, esquema_id, asignatura_id):
    _crear_componente_suelto(client_abierto, esquema_id, 60, nota=10)
    bloque_id = _crear_bloque(client_abierto, esquema_id, "Laboratorio", 40)
    _crear_componente_bloque(client_abierto, bloque_id, 100, nota=5)

    esquema = _esquema(client_abierto, asignatura_id)
    # 10*0.6 + 5*0.4 = 8
    assert esquema["resultado"]["media_ponderada"] == 8


def test_bloque_parcialmente_evaluado_no_cuenta_para_el_esquema(client_abierto, esquema_id, asignatura_id):
    _crear_componente_suelto(client_abierto, esquema_id, 60, nota=8)
    bloque_id = _crear_bloque(client_abierto, esquema_id, "Laboratorio", 40)
    _crear_componente_bloque(client_abierto, bloque_id, 100, nota=None)  # sin nota todavía

    esquema = _esquema(client_abierto, asignatura_id)
    assert esquema["bloques"][0]["resultado"]["media_ponderada"] is None
    # El bloque sin nota no aporta peso evaluado: la media del esquema es solo la del suelto.
    assert esquema["resultado"]["media_ponderada"] == 8
    assert esquema["resultado"]["peso_evaluado"] == 60


def test_borrar_bloque_borra_sus_componentes(client_abierto, esquema_id):
    bloque_id = _crear_bloque(client_abierto, esquema_id, "Laboratorio", 40)
    componente_id = _crear_componente_bloque(client_abierto, bloque_id, 100, nota=7)

    assert client_abierto.delete(f"/bloques/{bloque_id}").status_code == 204
    assert client_abierto.get(f"/componentes/{componente_id}").status_code == 404


def test_borrar_esquema_borra_sus_bloques(client_abierto, esquema_id, asignatura_id):
    bloque_id = _crear_bloque(client_abierto, esquema_id, "Laboratorio", 40)
    componente_id = _crear_componente_bloque(client_abierto, bloque_id, 100, nota=7)
    # No se puede borrar el único esquema: crea uno segundo para poder borrar el primero.
    client_abierto.post(f"/asignaturas/{asignatura_id}/esquemas", json={"nombre": "Otro"})

    r = client_abierto.delete(f"/esquemas/{esquema_id}")
    assert r.status_code == 204
    # El bloque y su componente se van con el esquema (cascade en models.py).
    assert client_abierto.get(f"/componentes/{componente_id}").status_code == 404


def test_componentes_efectivos_incluye_sueltos_y_bloques(client_abierto, esquema_id, asignatura_id):
    _crear_componente_suelto(client_abierto, esquema_id, 60, nota=8)
    bloque_id = _crear_bloque(client_abierto, esquema_id, "Laboratorio", 40)
    _crear_componente_bloque(client_abierto, bloque_id, 100, nota=6)

    esquema = _esquema(client_abierto, asignatura_id)
    efectivos = esquema["componentes_efectivos"]
    assert len(efectivos) == 2
    bloque_efectivo = next(e for e in efectivos if e.get("es_bloque"))
    assert bloque_efectivo["nombre"] == "Laboratorio"
    assert bloque_efectivo["nota"] == 6
    assert bloque_efectivo["porcentaje"] == 40


def test_mover_componente_a_un_bloque(client_abierto, esquema_id, asignatura_id):
    componente_id = _crear_componente_suelto(client_abierto, esquema_id, 30, nota=9)
    bloque_id = _crear_bloque(client_abierto, esquema_id, "Laboratorio", 40)

    r = client_abierto.put(f"/componentes/{componente_id}", json={"bloque_id": bloque_id})
    assert r.status_code == 200
    assert r.get_json()["bloque_id"] == bloque_id

    esquema = _esquema(client_abierto, asignatura_id)
    assert esquema["componentes"] == []  # ya no está suelto
    assert len(esquema["bloques"][0]["componentes"]) == 1


def test_bloque_porcentaje_fuera_de_rango_rechazado(client_abierto, esquema_id):
    r = client_abierto.post(f"/esquemas/{esquema_id}/bloques", json={"nombre": "X", "porcentaje": 150})
    assert r.status_code == 400


def test_estado_notas_cuenta_el_bloque_como_una_unidad(client_abierto, esquema_id, asignatura_id):
    # Suelto 60% con nota + bloque 40% con hijos 50/50 y notas: antes los hijos se
    # sumaban como sueltos (peso 160%) y la asignatura nunca salía como evaluada.
    _crear_componente_suelto(client_abierto, esquema_id, 60, nota=10)
    bloque_id = _crear_bloque(client_abierto, esquema_id, "Laboratorio", 40)
    _crear_componente_bloque(client_abierto, bloque_id, 50, nota=4)
    _crear_componente_bloque(client_abierto, bloque_id, 50, nota=4)

    asig = client_abierto.get(f"/asignaturas/{asignatura_id}").get_json()
    assert asig["estado_notas"] == "aprobada"
    assert asig["nota_actual"] == 7.6  # 10*0.6 + 4*0.4
    assert asig["evaluaciones_realizadas"] == 2  # suelto + bloque
    assert asig["evaluaciones_pendientes"] == 0


def test_duplicar_esquema_copia_estructura_sin_notas(client_abierto, esquema_id, asignatura_id):
    _crear_componente_suelto(client_abierto, esquema_id, 60, nota=8)
    bloque_id = _crear_bloque(client_abierto, esquema_id, "Laboratorio", 40)
    _crear_componente_bloque(client_abierto, bloque_id, 100, nota=6)

    r = client_abierto.post(f"/esquemas/{esquema_id}/duplicar")
    assert r.status_code == 201
    copia = r.get_json()
    assert copia["nombre"].endswith("(copia)")
    assert len(copia["componentes"]) == 1 and copia["componentes"][0]["nota"] is None
    assert copia["bloques"][0]["porcentaje"] == 40
    assert copia["bloques"][0]["componentes"][0]["nota"] is None
    assert copia["resultado"]["media_ponderada"] is None
    # El original conserva sus notas.
    original = client_abierto.get(f"/asignaturas/{asignatura_id}/esquemas").get_json()[0]
    assert original["resultado"]["media_ponderada"] == 7.2
