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


# --- CSRF global (Fase Web) ---

def _obtener_csrf_de_meta(html):
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert m, "no se encontró el <meta name=csrf-token> en la página"
    return m.group(1)


def test_csrf_valido_permite_peticion_mutable(client_csrf):
    token = _obtener_csrf_de_meta(client_csrf.get("/vista/dashboard").get_data(as_text=True))
    r = client_csrf.post(
        "/tareas", json={"titulo": "x", "tipo": "tarea_general"},
        headers={"X-CSRFToken": token},
    )
    assert r.status_code != 403


def test_csrf_ausente_es_rechazado_con_403_uniforme(client_csrf):
    r = client_csrf.post("/tareas", json={"titulo": "x", "tipo": "tarea_general"})
    assert r.status_code == 403
    assert r.get_json() == {"error": "invalid_csrf_token"}


def test_csrf_invalido_es_rechazado_con_403(client_csrf):
    r = client_csrf.post(
        "/tareas", json={"titulo": "x", "tipo": "tarea_general"},
        headers={"X-CSRFToken": "token-falso"},
    )
    assert r.status_code == 403
    assert r.get_json() == {"error": "invalid_csrf_token"}


def test_csrf_get_no_requiere_token(client_csrf):
    assert client_csrf.get("/asignaturas").status_code == 200


def test_csrf_cabecera_bearer_vacia_no_exime(client_csrf):
    """Una cabecera Authorization: Bearer  (sin token) o vacía no debe eximir de CSRF:
    solo cuenta como 'cliente de API' una cabecera bien formada y no vacía."""
    r = client_csrf.post(
        "/tareas", json={"titulo": "x", "tipo": "tarea_general"},
        headers={"Authorization": "Bearer "},
    )
    assert r.status_code == 403

    r = client_csrf.post(
        "/tareas", json={"titulo": "x", "tipo": "tarea_general"},
        headers={"X-GREELEC-KEY": ""},
    )
    assert r.status_code == 403


def test_csrf_cabecera_bearer_bien_formada_exime(client_csrf):
    """Sin GREELEC_LOCK_KEY configurada la clave nunca será 'correcta', pero eso lo
    decide la autenticación normal DESPUÉS: a efectos de CSRF, una cabecera Bearer
    bien formada basta para tratar la petición como no-navegador y eximirla."""
    r = client_csrf.post(
        "/tareas", json={"titulo": "x", "tipo": "tarea_general"},
        headers={"Authorization": "Bearer algo-no-vacio"},
    )
    assert r.status_code != 403

    r = client_csrf.post(
        "/tareas", json={"titulo": "x", "tipo": "tarea_general"},
        headers={"X-GREELEC-KEY": "algo-no-vacio"},
    )
    assert r.status_code != 403


def test_csrf_no_se_aplica_a_unlock_ni_lock(client_bloqueado):
    """/unlock y /lock conservan su propio control específico: el gate global no
    debe interferir ni exigir un segundo token distinto."""
    token = _extraer_csrf(client_bloqueado.get("/unlock").get_data(as_text=True))
    r = client_bloqueado.post("/unlock", data={"csrf_token": token, "clave": CLAVE})
    assert r.status_code != 403


# --- Rate limit progresivo en /unlock ---

def _fallar_login(client, veces, token_valido=None):
    for _ in range(veces):
        token = token_valido or _extraer_csrf(client.get("/unlock").get_data(as_text=True))
        client.post("/unlock", data={"csrf_token": token, "clave": "clave-mala"})


def test_rate_limit_bloquea_tras_varios_fallos_y_da_retry_after(client_bloqueado, monkeypatch):
    reloj = {"ahora": 1000.0}
    monkeypatch.setattr("routes.auth._reloj", lambda: reloj["ahora"])

    _fallar_login(client_bloqueado, 3)  # alcanza el umbral de bloqueo

    token = _extraer_csrf(client_bloqueado.get("/unlock").get_data(as_text=True))
    r = client_bloqueado.post("/unlock", data={"csrf_token": token, "clave": CLAVE})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) > 0


def test_rate_limit_deja_de_bloquear_pasado_el_backoff(client_bloqueado, monkeypatch):
    reloj = {"ahora": 2000.0}
    monkeypatch.setattr("routes.auth._reloj", lambda: reloj["ahora"])

    _fallar_login(client_bloqueado, 3)

    token = _extraer_csrf(client_bloqueado.get("/unlock").get_data(as_text=True))
    r = client_bloqueado.post("/unlock", data={"csrf_token": token, "clave": CLAVE})
    espera = int(r.headers["Retry-After"])
    assert r.status_code == 429

    reloj["ahora"] += espera  # avanza el reloj falso más allá del backoff, sin sleep real

    token = _extraer_csrf(client_bloqueado.get("/unlock").get_data(as_text=True))
    r = client_bloqueado.post("/unlock", data={"csrf_token": token, "clave": CLAVE})
    assert r.status_code == 302  # login correcto, ya no bloqueado


def test_rate_limit_se_reinicia_tras_login_correcto(client_bloqueado, monkeypatch):
    reloj = {"ahora": 3000.0}
    monkeypatch.setattr("routes.auth._reloj", lambda: reloj["ahora"])

    _fallar_login(client_bloqueado, 2)  # por debajo del umbral de bloqueo

    token = _extraer_csrf(client_bloqueado.get("/unlock").get_data(as_text=True))
    r = client_bloqueado.post("/unlock", data={"csrf_token": token, "clave": CLAVE})
    assert r.status_code == 302

    token_lock = _extraer_csrf(client_bloqueado.get("/vista/ajustes").get_data(as_text=True))
    client_bloqueado.post("/lock", data={"csrf_token": token_lock})  # cierra sesión para poder reintentar
    # Tras el login correcto el contador se reinicia: dos fallos más no deberían bastar para bloquear.
    _fallar_login(client_bloqueado, 2)
    token = _extraer_csrf(client_bloqueado.get("/unlock").get_data(as_text=True))
    r = client_bloqueado.post("/unlock", data={"csrf_token": token, "clave": "otra-mala"})
    assert r.status_code == 401  # clave incorrecta normal, no 429 (no estaba bloqueado)
