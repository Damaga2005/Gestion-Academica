def test_ajustes_muestra_la_bd_en_uso(client_abierto):
    html = client_abierto.get("/vista/ajustes").get_data(as_text=True)
    assert "Base de datos en uso" in html
    assert "tareas" in html and "documentos" in html
