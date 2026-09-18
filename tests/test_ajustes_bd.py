def test_ajustes_muestra_la_bd_en_uso(client_abierto):
    html = client_abierto.get("/vista/ajustes").get_data(as_text=True)
    assert "Base de datos en uso" in html
    assert "tareas" in html and "documentos" in html


def test_ajustes_avisa_si_hay_copia_en_conflicto(client_abierto, tmp_path, monkeypatch):
    from routes import vistas
    bd = tmp_path / "academico.db"
    bd.write_bytes(b"")
    (tmp_path / "academico.sync-conflict-20260918-101500-ABCDEFG.db").write_bytes(b"")
    monkeypatch.setitem(client_abierto.application.config, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{bd}")
    with client_abierto.application.app_context():
        assert len(vistas._info_base_datos()["conflictos"]) == 1


def test_changelog_muestra_la_ultima_fase(client_abierto):
    html = client_abierto.get("/vista/changelog").get_data(as_text=True)
    assert "Fase 11" in html and "Bloques de evaluación" in html
