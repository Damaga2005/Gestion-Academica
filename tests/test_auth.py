import re

CLAVE = "clave-test-1234"


def _extraer_csrf(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "no se encontró csrf_token en el formulario de /unlock"
    return m.group(1)


# --- Acceso abierto sin GREELEC_LOCK_KEY ---

def test_acceso_abierto_sin_lock_key(client_abierto):
    assert client_abierto.get("/asignaturas").status_code == 200
    assert client_abierto.get("/vista/dashboard").status_code == 200
    assert client_abierto.get("/tareas").status_code == 200


# --- Bloqueo activo sin autenticar ---

def test_api_sin_autenticar_devuelve_401_json(client_bloqueado):
    r = client_bloqueado.get("/asignaturas")
    assert r.status_code == 401
    assert r.get_json() == {"error": "authentication_required"}


def test_pagina_web_sin_autenticar_redirige_a_unlock(client_bloqueado):
    r = client_bloqueado.get("/vista/dashboard", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"] == "/unlock"


def test_rutas_publicas_siguen_accesibles_con_bloqueo_activo(client_bloqueado):
    assert client_bloqueado.get("/unlock").status_code == 200
    assert client_bloqueado.get("/api").status_code == 200


# --- Sesión web: clave correcta e incorrecta ---

def test_login_con_clave_incorrecta_no_autentica(client_bloqueado):
    token = _extraer_csrf(client_bloqueado.get("/unlock").get_data(as_text=True))
    r = client_bloqueado.post("/unlock", data={"csrf_token": token, "clave": "mala"})
    assert r.status_code == 401
    assert client_bloqueado.get("/asignaturas").status_code == 401


def test_login_con_clave_correcta_autentica_y_preserva_destino(client_bloqueado):
    # Primero se intenta acceder a una página protegida: debe recordarse como destino.
    client_bloqueado.get("/vista/dashboard", follow_redirects=False)

    token = _extraer_csrf(client_bloqueado.get("/unlock").get_data(as_text=True))
    r = client_bloqueado.post(
        "/unlock", data={"csrf_token": token, "clave": CLAVE}, follow_redirects=False
    )
    assert r.status_code == 302

    # Tras autenticar, tanto la web como la API deben funcionar.
    assert client_bloqueado.get("/vista/dashboard").status_code == 200
    assert client_bloqueado.get("/asignaturas").status_code == 200


def test_login_csrf_invalido_es_rechazado(client_bloqueado):
    r = client_bloqueado.post("/unlock", data={"csrf_token": "token-falso", "clave": CLAVE})
    assert r.status_code == 400
    assert client_bloqueado.get("/asignaturas").status_code == 401


def test_lock_cierra_sesion(client_bloqueado):
    token = _extraer_csrf(client_bloqueado.get("/unlock").get_data(as_text=True))
    client_bloqueado.post("/unlock", data={"csrf_token": token, "clave": CLAVE})
    assert client_bloqueado.get("/asignaturas").status_code == 200

    token2 = _extraer_csrf(client_bloqueado.get("/vista/ajustes").get_data(as_text=True))
    r = client_bloqueado.post("/lock", data={"csrf_token": token2}, follow_redirects=False)
    assert r.status_code == 302
    assert client_bloqueado.get("/asignaturas").status_code == 401


# --- Token de API: correcto e incorrecto, ambos formatos de cabecera ---

def test_api_key_incorrecta_devuelve_401(client_bloqueado):
    r = client_bloqueado.get("/asignaturas", headers={"X-GREELEC-KEY": "incorrecta"})
    assert r.status_code == 401


def test_api_key_correcta_x_greelec_key(client_bloqueado):
    r = client_bloqueado.get("/asignaturas", headers={"X-GREELEC-KEY": CLAVE})
    assert r.status_code == 200


def test_api_key_correcta_bearer(client_bloqueado):
    r = client_bloqueado.get("/asignaturas", headers={"Authorization": f"Bearer {CLAVE}"})
    assert r.status_code == 200


def test_clave_nunca_se_filtra_en_la_respuesta(client_bloqueado):
    r = client_bloqueado.get("/asignaturas", headers={"X-GREELEC-KEY": "incorrecta-xyz"})
    cuerpo = r.get_data(as_text=True)
    assert CLAVE not in cuerpo
    assert "incorrecta-xyz" not in cuerpo


# --- Cobertura de métodos GET/POST/PATCH/DELETE ---

def test_proteccion_cubre_todos_los_metodos_http(client_bloqueado):
    casos = [
        ("GET", "/asignaturas"),
        ("POST", "/tareas"),
        ("PATCH", "/api/asignaturas/1/estado"),
        ("DELETE", "/hitos/1"),
        ("GET", "/documentos/1"),
        ("POST", "/backup/importar"),
    ]
    for metodo, ruta in casos:
        r = client_bloqueado.open(ruta, method=metodo)
        assert r.status_code == 401, f"{metodo} {ruta} debería exigir autenticación"

    # Con la clave correcta, los mismos métodos dejan de dar 401 (pueden dar otros
    # códigos por datos de la petición, pero nunca 401).
    for metodo, ruta in casos:
        r = client_bloqueado.open(ruta, method=metodo, headers={"X-GREELEC-KEY": CLAVE})
        assert r.status_code != 401, f"{metodo} {ruta} no debería dar 401 con la clave correcta"
