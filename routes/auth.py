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

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

auth_bp = Blueprint("auth", __name__)

# Rutas accesibles sin autenticar aunque el bloqueo esté activo (spec: solo estas quedan públicas)
RUTAS_PUBLICAS_EXACTAS = {"/unlock", "/lock", "/api"}
PREFIJOS_PUBLICOS = ("/static/",)


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
        return {
            "lock_activo": lock_key_configurada(),
            "csrf_token": _generar_csrf_token() if session.get("autenticado") else "",
        }


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

    if not _validar_csrf(request.form.get("csrf_token", "")):
        return render_template(
            "unlock.html", csrf_token=_generar_csrf_token(),
            error="Formulario caducado, inténtalo de nuevo.",
        ), 400

    if _clave_correcta(request.form.get("clave", "")):
        destino = session.pop("destino_tras_unlock", None)
        session.clear()
        session["autenticado"] = True
        session.permanent = True
        return redirect(destino or url_for("vistas.dashboard"))

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
