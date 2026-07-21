"""
Tests de la Fase "Calendario académico y horario recurrente" (spec punto 12):
siglas, calendario académico ampliado, horario recurrente, conflictos y export .ics.
"""

import pytest


# --- Siglas ---

def test_crear_asignatura_con_siglas(client_abierto):
    aid = client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]
    r = client_abierto.put(f"/asignaturas/{aid}", json={"siglas": "DSED"})
    assert r.status_code == 200
    assert r.get_json()["siglas"] == "DSED"


def test_normalizar_siglas_a_mayusculas(client_abierto):
    aid = client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]
    r = client_abierto.put(f"/asignaturas/{aid}", json={"siglas": "  dsed  "})
    assert r.status_code == 200
    assert r.get_json()["siglas"] == "DSED"


def test_impedir_siglas_duplicadas(client_abierto):
    a, b = client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[:2]
    client_abierto.put(f"/asignaturas/{a['id']}", json={"siglas": "DSED"})
    r = client_abierto.put(f"/asignaturas/{b['id']}", json={"siglas": "dsed"})
    assert r.status_code == 409


def test_resolver_asignatura_por_siglas(client_abierto):
    aid = client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]
    client_abierto.put(f"/asignaturas/{aid}", json={"siglas": "DSED"})

    r = client_abierto.get("/asignaturas/DSED")
    assert r.status_code == 200
    assert r.get_json()["id"] == aid

    r = client_abierto.get(f"/asignaturas/{aid}")
    assert r.status_code == 200

    assert client_abierto.get("/asignaturas/NOEXISTE").status_code == 404


# --- Calendario académico ---

def test_crear_examen_con_hora_y_aula(client_abierto):
    aid = client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]
    r = client_abierto.post("/tareas", json={
        "titulo": "Parcial 1", "fecha": "2026-10-10", "tipo": "examen_parcial",
        "hora_inicio": "10:30", "hora_fin": "12:30", "aula": "2.14", "asignatura_id": aid,
    })
    assert r.status_code == 201
    data = r.get_json()
    assert data["hora_inicio"] == "10:30" and data["hora_fin"] == "12:30" and data["aula"] == "2.14"


def test_examen_acepta_siglas_como_asignatura(client_abierto):
    aid = client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]
    client_abierto.put(f"/asignaturas/{aid}", json={"siglas": "DSED"})
    r = client_abierto.post("/tareas", json={
        "titulo": "Final", "fecha": "2026-10-10", "tipo": "examen_final", "asignatura_id": "dsed",
    })
    assert r.status_code == 201
    assert r.get_json()["asignatura_id"] == aid


def test_hora_fin_debe_ser_posterior_a_hora_inicio(client_abierto):
    r = client_abierto.post("/tareas", json={
        "titulo": "X", "fecha": "2026-10-10", "hora_inicio": "12:00", "hora_fin": "10:00",
    })
    assert r.status_code == 400


# --- Horario recurrente ---

@pytest.fixture
def asignatura_con_siglas(client_abierto):
    aid = client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]
    client_abierto.put(f"/asignaturas/{aid}", json={"siglas": "DSED"})
    return aid


def test_crear_clase_semanal(client_abierto, asignatura_con_siglas):
    r = client_abierto.post("/horarios", json={
        "asignatura_id": "DSED", "tipo": "teoria", "dia_semana": 1,
        "hora_inicio": "09:00", "hora_fin": "11:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18", "intervalo_semanas": 1,
    })
    assert r.status_code == 201
    horario = r.get_json()
    assert horario["conflictos"] == []

    sesiones = client_abierto.get(f"/horarios/{horario['id']}/sesiones").get_json()
    assert sesiones[0] == "2026-09-07"  # fecha_inicio ya es lunes
    assert all(s <= "2026-12-18" for s in sesiones)


def test_crear_laboratorio_quincenal(client_abierto, asignatura_con_siglas):
    r = client_abierto.post("/horarios", json={
        "asignatura_id": "DSED", "tipo": "laboratorio", "dia_semana": 2,
        "hora_inicio": "15:00", "hora_fin": "17:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18", "intervalo_semanas": 2,
    })
    assert r.status_code == 201
    sesiones = client_abierto.get(f"/horarios/{r.get_json()['id']}/sesiones").get_json()
    # Quincenal: la diferencia entre sesiones consecutivas es siempre 14 días
    for i in range(1, len(sesiones)):
        from datetime import date
        a = date.fromisoformat(sesiones[i - 1])
        b = date.fromisoformat(sesiones[i])
        assert (b - a).days == 14


def test_no_generar_sesiones_fuera_del_intervalo(client_abierto, asignatura_con_siglas):
    r = client_abierto.post("/horarios", json={
        "asignatura_id": "DSED", "tipo": "teoria", "dia_semana": 1,
        "hora_inicio": "09:00", "hora_fin": "11:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-09-20", "intervalo_semanas": 1,
    })
    sesiones = client_abierto.get(f"/horarios/{r.get_json()['id']}/sesiones").get_json()
    assert all("2026-09-07" <= s <= "2026-09-20" for s in sesiones)
    assert len(sesiones) == 2  # dos lunes: 7 y 14 (el 21 ya se pasa del fecha_fin=20)


def test_editar_toda_la_serie(client_abierto, asignatura_con_siglas):
    hid = client_abierto.post("/horarios", json={
        "asignatura_id": "DSED", "tipo": "teoria", "dia_semana": 1,
        "hora_inicio": "09:00", "hora_fin": "11:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18",
    }).get_json()["id"]

    r = client_abierto.put(f"/horarios/{hid}", json={"aula": "Nueva aula", "hora_inicio": "10:00", "hora_fin": "12:00"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["aula"] == "Nueva aula" and data["hora_inicio"] == "10:00"


def test_eliminar_toda_la_serie(client_abierto, asignatura_con_siglas):
    hid = client_abierto.post("/horarios", json={
        "asignatura_id": "DSED", "tipo": "teoria", "dia_semana": 1,
        "hora_inicio": "09:00", "hora_fin": "11:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18",
    }).get_json()["id"]

    assert client_abierto.delete(f"/horarios/{hid}").status_code == 204
    assert client_abierto.get(f"/horarios/{hid}").status_code == 404


def test_validaciones_horario(client_abierto, asignatura_con_siglas):
    base = {
        "asignatura_id": "DSED", "tipo": "teoria", "dia_semana": 1,
        "hora_inicio": "09:00", "hora_fin": "11:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18",
    }
    assert client_abierto.post("/horarios", json={**base, "tipo": "invalido"}).status_code == 422
    assert client_abierto.post("/horarios", json={**base, "dia_semana": 6}).status_code == 422
    assert client_abierto.post("/horarios", json={**base, "hora_inicio": "12:00", "hora_fin": "11:00"}).status_code == 400
    assert client_abierto.post("/horarios", json={**base, "fecha_inicio": "2026-12-18", "fecha_fin": "2026-09-07"}).status_code == 400
    assert client_abierto.post("/horarios", json={**base, "intervalo_semanas": 3}).status_code == 422


# --- Conflictos ---

def test_detectar_conflictos_entre_horario_y_examen(client_abierto, asignatura_con_siglas):
    client_abierto.post("/horarios", json={
        "asignatura_id": "DSED", "tipo": "laboratorio", "dia_semana": 2,
        "hora_inicio": "15:00", "hora_fin": "17:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18",
    })
    # 2026-09-08 es martes: cae en la serie anterior
    r = client_abierto.post("/tareas", json={
        "titulo": "Examen sorpresa", "fecha": "2026-09-08", "tipo": "examen_parcial",
        "hora_inicio": "16:00", "hora_fin": "18:00",
    })
    assert r.status_code == 201  # spec: permite guardar igualmente
    conflictos = r.get_json()["conflictos"]
    assert len(conflictos) == 1 and conflictos[0]["tipo"] == "horario"


def test_comprobar_conflictos_no_bloquea(client_abierto, asignatura_con_siglas):
    client_abierto.post("/tareas", json={
        "titulo": "Entrega", "fecha": "2026-10-01", "hora_inicio": "09:00", "hora_fin": "10:00",
    })
    r = client_abierto.post("/calendario/comprobar-conflictos", json={
        "fecha": "2026-10-01", "hora_inicio": "09:30", "hora_fin": "10:30",
    })
    assert r.status_code == 200
    assert len(r.get_json()["conflictos"]) == 1


# --- Exportación .ics ---

def test_exportar_evento_puntual_ics(client_abierto, asignatura_con_siglas):
    tid = client_abierto.post("/tareas", json={
        "titulo": "Final", "fecha": "2026-10-10", "tipo": "examen_final",
        "hora_inicio": "10:30", "hora_fin": "12:30", "asignatura_id": "DSED",
    }).get_json()["id"]

    r = client_abierto.get(f"/tareas/{tid}/ics")
    assert r.status_code == 200
    assert r.content_type.startswith("text/calendar")
    texto = r.get_data(as_text=True)
    assert "BEGIN:VEVENT" in texto and "DTSTART:20261010T103000" in texto


def test_exportar_serie_recurrente_ics_con_rrule(client_abierto, asignatura_con_siglas):
    hid = client_abierto.post("/horarios", json={
        "asignatura_id": "DSED", "tipo": "laboratorio", "dia_semana": 2,
        "hora_inicio": "15:00", "hora_fin": "17:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18", "intervalo_semanas": 2,
    }).get_json()["id"]

    r = client_abierto.get(f"/horarios/{hid}/ics")
    assert r.status_code == 200
    texto = r.get_data(as_text=True)
    assert "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU" in texto


def test_exportar_calendario_completo_ics(client_abierto, asignatura_con_siglas):
    client_abierto.post("/tareas", json={"titulo": "Evento", "fecha": "2026-10-01"})
    client_abierto.post("/horarios", json={
        "asignatura_id": "DSED", "tipo": "teoria", "dia_semana": 1,
        "hora_inicio": "09:00", "hora_fin": "11:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18",
    })
    r = client_abierto.get("/calendario/ics")
    assert r.status_code == 200
    assert r.get_data(as_text=True).count("BEGIN:VEVENT") == 2


# --- Migración ---

def test_migracion_conserva_datos_de_esta_fase(app_abierta):
    """Complementa tests/test_migracion.py: aquí se comprueba específicamente que
    siglas + tarea_evento ampliada + horario_clase sobreviven un ciclo de reseed."""
    with app_abierta.app_context():
        from models import Asignatura
        from seed import poblar_datos_iniciales

        aid = Asignatura.query.filter_by(tipo="obligatoria").first().id
        Asignatura.query.get(aid).siglas = "DSED"
        from models import db
        db.session.commit()

        poblar_datos_iniciales()  # reseed idempotente

        asignatura = Asignatura.query.get(aid)
        assert asignatura.siglas == "DSED"  # el reseed no debe pisar el dato manual
