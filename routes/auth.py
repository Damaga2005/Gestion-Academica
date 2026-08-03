"""
Capa de seguridad opcional (Fase 11, punto 3), activada solo si se define GREELEC_LOCK_KEY.

Con la variable vacía o sin definir, la app se comporta exactamente igual que hasta ahora
(sin ningún cambio de comportamiento): esto se decide en tiempo de petición, no al arrancar,
así que basta con (des)definir la variable de entorno para activar/desactivar el bloqueo.

Dos mecanismos de autenticación, ambos comparando contra la clave con hmac.compare_digest
para evitar timing attacks, y sin guardar ni loguear nunca la clave en ningún sitio:
- Sesión web: formulario /unlock -> guarda solo un flag en la sesión (nunca la clave).
- API: cabecera 'Authorization: Bearer <clave>' o 'X-GREELEC-KEY: <clave>'.
"""
import hmac
import os
import secrets
import time

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

auth_bp = Blueprint("auth", __name__)

# Rutas accesibles sin autenticar aunque el bloqueo esté activo (spec: solo estas quedan públicas)
RUTAS_PUBLICAS_EXACTAS = {"/unlock", "/lock", "/api"}
PREFIJOS_PUBLICOS = ("/static/",)

# --- Rate limit progresivo para /unlock ---
# En memoria, de un solo proceso: suficiente para esta app personal (spec Fase Web
# punto 5). `_reloj` es sustituible en los tests para no depender de time.sleep real.
_reloj = time.monotonic
_intentos_fallidos = {}  # ip -> {"fallos": int, "bloqueado_hasta": float, "ultimo": float}
_INTENTOS_ANTES_DE_BLOQUEAR = 3
_BACKOFF_BASE_SEGUNDOS = 2
_BACKOFF_MAXIMO_SEGUNDOS = 300  # nunca un bloqueo permanente
_ENTRADA_INACTIVA_SEGUNDOS = 3600  # se olvida una IP tras una hora sin intentos


def _limpiar_intentos_viejos(ahora):
    viejas = [ip for ip, info in _intentos_fallidos.items() if ahora - info["ultimo"] > _ENTRADA_INACTIVA_SEGUNDOS]
    for ip in viejas:
        del _intentos_fallidos[ip]


def _segundos_de_espera(ip):
    ahora = _reloj()
    _limpiar_intentos_viejos(ahora)
    info = _intentos_fallidos.get(ip)
    if not info:
        return 0
    return max(0, info["bloqueado_hasta"] - ahora)


def _registrar_intento_fallido(ip):
    ahora = _reloj()
    info = _intentos_fallidos.setdefault(ip, {"fallos": 0, "bloqueado_hasta": 0.0, "ultimo": ahora})
    info["fallos"] += 1
    info["ultimo"] = ahora
    exceso = info["fallos"] - _INTENTOS_ANTES_DE_BLOQUEAR
    if exceso >= 0:
        espera = min(_BACKOFF_BASE_SEGUNDOS * (2 ** exceso), _BACKOFF_MAXIMO_SEGUNDOS)
        info["bloqueado_hasta"] = ahora + espera


def _resetear_intentos(ip):
    _intentos_fallidos.pop(ip, None)


def lock_key_configurada():
    return bool(os.environ.get("GREELEC_LOCK_KEY", "").strip())


def _clave_real():
    return os.environ.get("GREELEC_LOCK_KEY", "")


def _clave_correcta(intentada):
    clave_real = _clave_real()
    if not clave_real or not intentada:
        return False
    return hmac.compare_digest(intentada.encode("utf-8"), clave_real.encode("utf-8"))


def _extraer_clave_api(peticion):
    """Devuelve la clave recibida por cabecera (Authorization: Bearer o X-GREELEC-KEY), o None si no hay ninguna."""
    auth_header = peticion.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):].strip()
    x_key = peticion.headers.get("X-GREELEC-KEY")
    if x_key is not None:
        return x_key.strip()
    return None


def _generar_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


def _validar_csrf(token_recibido):
    token_esperado = session.get("_csrf_token")
    return bool(token_esperado) and bool(token_recibido) and hmac.compare_digest(token_esperado, token_recibido)


def _tiene_cabecera_api_valida(peticion):
    """Cierto solo si la petición se autentica de verdad como cliente de API: hace
    falta que GREELEC_LOCK_KEY esté configurada Y que la clave recibida (Bearer o
    X-GREELEC-KEY) sea la correcta. No basta con que la cabecera tenga la forma
    esperada: con el bloqueo desactivado (estado por defecto de la app) esa
    cabecera no significa nada, y aceptarla como señal de "cliente de API" eximía
    de CSRF a cualquiera que mandara un Authorization cualquiera."""
    if not lock_key_configurada():
        return False
    clave = _extraer_clave_api(peticion)
    return clave is not None and _clave_correcta(clave)


def _token_csrf_de_la_peticion():
    token = request.headers.get("X-CSRFToken")
    if token:
        return token
    if request.is_json:
        token = (request.get_json(silent=True) or {}).get("csrf_token")
        if token:
            return token
    return request.form.get("csrf_token")


def _es_ruta_publica(path):
    if path in RUTAS_PUBLICAS_EXACTAS:
        return True
    return any(path.startswith(prefijo) for prefijo in PREFIJOS_PUBLICOS)


def _es_pagina_html(path):
    """Distingue peticiones de navegador (páginas /vista/*) de la API JSON, para decidir
    si conviene redirigir a /unlock o devolver un 401 JSON."""
    return path == "/" or path.startswith("/vista/")


def registrar_gate_autenticacion(app):
    @app.before_request
    def _exigir_autenticacion():
        if not lock_key_configurada():
            return  # sin GREELEC_LOCK_KEY, la app queda abierta (comportamiento de siempre)

        if _es_ruta_publica(request.path):
            return

        clave_api = _extraer_clave_api(request)
        if clave_api is not None:
            if _clave_correcta(clave_api):
                return
            return jsonify({"error": "authentication_required"}), 401

        if session.get("autenticado"):
            return

        if _es_pagina_html(request.path):
            session["destino_tras_unlock"] = (
                request.full_path if request.query_string else request.path
            )
            return redirect(url_for("auth.formulario_unlock"))

        return jsonify({"error": "authentication_required"}), 401

    @app.context_processor
    def _inyectar_datos_auth():
        # El token CSRF existe por sesión independientemente de si hay login activo
        # (spec Fase Web: "tokens CSRF por sesión"), porque la protección CSRF global
        # cubre TODAS las peticiones mutables, no solo cuando GREELEC_LOCK_KEY está
        # activa.
        return {
            "lock_activo": lock_key_configurada(),
            "csrf_token": _generar_csrf_token(),
        }


def registrar_csrf_global(app):
    """Protección CSRF global para POST/PUT/PATCH/DELETE (spec Fase Web punto 1).
    Debe registrarse DESPUÉS de registrar_gate_autenticacion(app): así el gate de
    autenticación ya ha podido devolver 401/redirigir antes de llegar aquí.

    /unlock y /lock quedan fuera: ya tienen su propia validación CSRF específica
    (ligada al flujo de esos dos formularios en concreto) y esta comprobación
    global no debe duplicarla ni contradecirla."""
    RUTAS_CSRF_PROPIO = {"/unlock", "/lock"}

    @app.before_request
    def _exigir_csrf_global():
        if not current_app.config.get("WTF_CSRF_ENABLED", True):
            return  # desactivado explícitamente (p. ej. en tests que no cubren CSRF)
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return
        if request.path in RUTAS_CSRF_PROPIO:
            return
        if _tiene_cabecera_api_valida(request):
            return  # cliente de API (Bearer/X-GREELEC-KEY bien formado): exento
        if not _validar_csrf(_token_csrf_de_la_peticion()):
            return jsonify({"error": "invalid_csrf_token"}), 403


@auth_bp.get("/unlock")
def formulario_unlock():
    if not lock_key_configurada() or session.get("autenticado"):
        destino = session.pop("destino_tras_unlock", None) or url_for("vistas.dashboard")
        return redirect(destino)
    return render_template("unlock.html", csrf_token=_generar_csrf_token(), error=None)


@auth_bp.post("/unlock")
def procesar_unlock():
    if not lock_key_configurada():
        return redirect(url_for("vistas.dashboard"))

    ip = request.remote_addr or "desconocida"
    espera = _segundos_de_espera(ip)
    if espera > 0:
        respuesta = render_template(
            "unlock.html", csrf_token=_generar_csrf_token(),
            error=f"Demasiados intentos. Inténtalo de nuevo en {int(espera) + 1} s.",
        )
        resp = current_app.response_class(respuesta, status=429)
        resp.headers["Retry-After"] = str(int(espera) + 1)
        return resp

    if not _validar_csrf(request.form.get("csrf_token", "")):
        return render_template(
            "unlock.html", csrf_token=_generar_csrf_token(),
            error="Formulario caducado, inténtalo de nuevo.",
        ), 400

    if _clave_correcta(request.form.get("clave", "")):
        _resetear_intentos(ip)
        destino = session.pop("destino_tras_unlock", None)
        session.clear()
        session["autenticado"] = True
        session.permanent = True
        return redirect(destino or url_for("vistas.dashboard"))

    _registrar_intento_fallido(ip)
    return render_template(
        "unlock.html", csrf_token=_generar_csrf_token(), error="Clave incorrecta.",
    ), 401


@auth_bp.post("/lock")
def cerrar_sesion():
    if session.get("autenticado") and not _validar_csrf(request.form.get("csrf_token", "")):
        return render_template("unlock.html", csrf_token=_generar_csrf_token(),
                                error="No se pudo cerrar sesión, recarga la página."), 400
    session.clear()
    return redirect(url_for("auth.formulario_unlock"))
