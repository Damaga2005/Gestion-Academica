import pytest

from app import create_app


def _crear_app(tmp_path, monkeypatch, lock_key=None, seed=False):
    monkeypatch.delenv("GREELEC_LOCK_KEY", raising=False)
    if lock_key:
        monkeypatch.setenv("GREELEC_LOCK_KEY", lock_key)

    db_path = tmp_path / "test.db"
    docs_path = tmp_path / "documentos"
    app = create_app(
        auto_seed=False,
        database_uri=f"sqlite:///{db_path}",
        documentos_dir=str(docs_path),
    )
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    if seed:
        with app.app_context():
            from seed import poblar_datos_iniciales
            poblar_datos_iniciales()

    return app


@pytest.fixture
def app_abierta(tmp_path, monkeypatch):
    """App sin GREELEC_LOCK_KEY (comportamiento de siempre) y con datos sembrados."""
    return _crear_app(tmp_path, monkeypatch, lock_key=None, seed=True)


@pytest.fixture
def app_bloqueada(tmp_path, monkeypatch):
    """App con GREELEC_LOCK_KEY definida y datos sembrados."""
    return _crear_app(tmp_path, monkeypatch, lock_key="clave-test-1234", seed=True)


@pytest.fixture
def app_vacia(tmp_path, monkeypatch):
    """App sin GREELEC_LOCK_KEY y SIN sembrar (para tests de migración/seed)."""
    return _crear_app(tmp_path, monkeypatch, lock_key=None, seed=False)


@pytest.fixture
def client_abierto(app_abierta):
    return app_abierta.test_client()


@pytest.fixture
def client_bloqueado(app_bloqueada):
    return app_bloqueada.test_client()
