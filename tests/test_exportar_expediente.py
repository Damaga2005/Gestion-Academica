def test_expediente_csv_una_fila_por_asignatura(client_abierto):
    r = client_abierto.get("/exportar/expediente.csv")
    assert r.status_code == 200
    assert "attachment" in r.headers["Content-Disposition"]
    texto = r.get_data(as_text=True)
    assert texto.startswith("﻿Cuatrimestre;Siglas;Asignatura;ECTS")
    filas = texto.strip().splitlines()
    total = len(client_abierto.get("/asignaturas").get_json())
    assert len(filas) - 1 == total
