"""
Borrar una asignatura debe limpiar todo lo que cuelga de ella sin relación
cascade en el modelo (TareaEvento, HorarioClase): sin esto, esas filas se
quedan huérfanas apuntando a una asignatura que ya no existe.
"""


def _asignatura_id(client_abierto):
    return client_abierto.get("/asignaturas?tipo=obligatoria").get_json()[0]["id"]


def test_borrar_asignatura_borra_su_horario(client_abierto):
    asignatura_id = _asignatura_id(client_abierto)
    r = client_abierto.post("/horarios", json={
        "asignatura_id": asignatura_id, "tipo": "teoria", "dia_semana": 1,
        "hora_inicio": "09:00", "hora_fin": "11:00",
        "fecha_inicio": "2026-09-07", "fecha_fin": "2026-12-18", "intervalo_semanas": 1,
    })
    assert r.status_code == 201
    horario_id = r.get_json()["id"]

    assert client_abierto.delete(f"/asignaturas/{asignatura_id}").status_code == 204
    assert client_abierto.get(f"/horarios/{horario_id}").status_code == 404


def test_borrar_asignatura_borra_sus_tareas_y_espacios(client_abierto):
    asignatura_id = _asignatura_id(client_abierto)
    r = client_abierto.post("/tareas", json={
        "titulo": "Final", "fecha": "2026-11-20",
        "tipo": "examen_final", "asignatura_id": asignatura_id,
    })
    tarea_id = r.get_json()["id"]
    espacio_id = client_abierto.get(f"/tareas/{tarea_id}/espacio-estudio").get_json()["id"]

    assert client_abierto.delete(f"/asignaturas/{asignatura_id}").status_code == 204
    assert client_abierto.get(f"/tareas/{tarea_id}").status_code == 404
    assert client_abierto.get(f"/espacios-estudio/{espacio_id}").status_code == 404
