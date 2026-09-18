import io

ICS = "\r\n".join([
    "BEGIN:VCALENDAR", "VERSION:2.0",
    "BEGIN:VEVENT", "SUMMARY:[G13] Estudi Previ P0\\, 1a sessió",
    "DTSTART:20260923T080000Z",
    "CATEGORIES:230911 - DISSENY DIGITAL (Curs 10)",
    "URL:https://atenea.upc.edu/mod/assign/view.php?id=1", "END:VEVENT",
    "BEGIN:VEVENT", "SUMMARY:Qüestionari inicial Tema 2",
    "DTSTART:20261006T195500Z",
    "CATEGORIES:230920 - SISTEMES DE MESURA (Curs 10)",
    "URL:https://atenea.upc.edu/mod/quiz/view.php?id=2", "END:VEVENT",
    "BEGIN:VEVENT", "SUMMARY:Invierno", "DTSTART:20270120T100000Z",
    "CATEGORIES:Curso desconocido", "END:VEVENT",
    "BEGIN:VEVENT", "SUMMARY:Sin fecha", "END:VEVENT",
    "END:VCALENDAR", "",
])


def _analizar(client, texto=ICS):
    return client.post(
        "/calendario/importar-ics/analizar",
        data={"archivo": (io.BytesIO(texto.encode("utf-8")), "cal.ics")},
        content_type="multipart/form-data",
    )


def test_analizar_horas_tipos_y_asignatura(client_abierto):
    r = _analizar(client_abierto)
    assert r.status_code == 200
    ev = {e["titulo"]: e for e in r.get_json()["eventos"]}
    assert len(ev) == 3  # el evento sin fecha se ignora
    p0 = ev["[G13] Estudi Previ P0, 1a sessió"]
    assert (p0["fecha"], p0["hora_fin"], p0["tipo"]) == ("2026-09-23", "10:00", "entrega")  # verano: UTC+2
    assert ev["Qüestionari inicial Tema 2"]["hora_fin"] == "21:55"
    assert ev["Qüestionari inicial Tema 2"]["tipo"] == "tarea_general"
    assert ev["Invierno"]["hora_fin"] == "11:00"  # invierno: UTC+1
    assert ev["Invierno"]["asignatura_id"] is None  # sin parecido: lo elige el usuario


def test_analizar_no_escribe_y_rechaza_no_ics(client_abierto):
    antes = len(client_abierto.get("/tareas").get_json())
    _analizar(client_abierto)
    assert len(client_abierto.get("/tareas").get_json()) == antes
    assert _analizar(client_abierto, "hola").status_code == 400


def test_importar_crea_y_omite_duplicados(client_abierto):
    evento = {"titulo": "Lliurament 1", "fecha": "2026-10-09", "hora_fin": "23:59", "tipo": "entrega", "asignatura_id": None}
    r = client_abierto.post("/calendario/importar-ics", json={"eventos": [evento]})
    assert r.get_json() == {"creadas": 1, "omitidas": 0}
    r = client_abierto.post("/calendario/importar-ics", json={"eventos": [evento]})
    assert r.get_json() == {"creadas": 0, "omitidas": 1}
    ev = _analizar(client_abierto, ICS.replace("Invierno", "Lliurament 1").replace("20270120T100000Z", "20261009T215900Z")).get_json()["eventos"]
    assert next(e for e in ev if e["titulo"] == "Lliurament 1")["duplicado"] is True


def test_importar_valida_tipo(client_abierto):
    r = client_abierto.post("/calendario/importar-ics", json={"eventos": [{"titulo": "X", "fecha": "2026-10-09", "tipo": "raro"}]})
    assert r.status_code == 400


def test_pagina_calendario_carga_el_importador(client_abierto):
    html = client_abierto.get("/vista/calendario").get_data(as_text=True)
    assert "btn-importar-ics" in html and "importar-ics.js" in html
