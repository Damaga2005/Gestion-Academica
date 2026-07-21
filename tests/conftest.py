import pytest

from app import create_app


@pytest.fixture(autouse=True)
def _reset_rate_limit_unlock():
    """El contador de intentos fallidos de /unlock vive en un dict a nivel de módulo
    (deliberado: es un rate limit en memoria de un solo proceso). Sin resetearlo,
    los fallos de un test contaminarían el siguiente."""
    from routes import auth as auth_module
    auth_module._intentos_fallidos.clear()
    yield
    auth_module._intentos_fallidos.clear()


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


@pytest.fixture
def app_csrf(tmp_path, monkeypatch):
    """App abierta (sin GREELEC_LOCK_KEY) pero con la protección CSRF global
    realmente activa, para probarla de forma aislada del resto de tests (que la
    desactivan a propósito para no tener que enviar token en cada petición)."""
    app = _crear_app(tmp_path, monkeypatch, lock_key=None, seed=True)
    app.config["WTF_CSRF_ENABLED"] = True
    return app


@pytest.fixture
def client_csrf(app_csrf):
    return app_csrf.test_client()
