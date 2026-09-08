"""
Test del aviso nativo de Windows al arrancar (_avisar_notificaciones_urgentes en
escritorio.py): solo dispara con avisos nivel rojo, agrega el mensaje si hay
varios, y no revienta si winotify falla (spec "qué mejorar": notificaciones
seguía siendo un backend sin ningún punto de acceso desde la UI).
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import escritorio


def _crear_tarea_atrasada(client, titulo="Tarea atrasada"):
    r = client.post("/tareas", json={
        "titulo": titulo, "fecha": (date.today() - timedelta(days=1)).isoformat(),
    })
    assert r.status_code == 201


def test_sin_avisos_rojos_no_muestra_nada(app_abierta):
    with patch("winotify.Notification") as MockNotification:
        escritorio._avisar_notificaciones_urgentes(app_abierta)
        MockNotification.assert_not_called()


def test_un_aviso_rojo_muestra_su_mensaje(app_abierta):
    client = app_abierta.test_client()
    _crear_tarea_atrasada(client, "Entrega TFG")

    instancia = MagicMock()
    with patch("winotify.Notification", return_value=instancia) as MockNotification:
        escritorio._avisar_notificaciones_urgentes(app_abierta)

    MockNotification.assert_called_once()
    # con un único aviso se manda su mensaje tal cual (no el título): comprueba que
    # es justo el texto que calcular_notificaciones() genera para una tarea atrasada.
    assert "atrasada" in MockNotification.call_args.kwargs["msg"]
    instancia.show.assert_called_once()


def test_varios_avisos_rojos_los_agrega(app_abierta):
    client = app_abierta.test_client()
    _crear_tarea_atrasada(client, "Primera")
    _crear_tarea_atrasada(client, "Segunda")

    instancia = MagicMock()
    with patch("winotify.Notification", return_value=instancia) as MockNotification:
        escritorio._avisar_notificaciones_urgentes(app_abierta)

    mensaje = MockNotification.call_args.kwargs["msg"]
    assert "2 avisos urgentes" in mensaje
    assert "Primera" in mensaje and "Segunda" in mensaje


def test_fallo_al_mostrar_el_toast_no_propaga_excepcion(app_abierta):
    client = app_abierta.test_client()
    _crear_tarea_atrasada(client)

    instancia = MagicMock()
    instancia.show.side_effect = RuntimeError("sin AUMID registrado")
    with patch("winotify.Notification", return_value=instancia):
        escritorio._avisar_notificaciones_urgentes(app_abierta)  # no debe lanzar


def _sembrar_racha(app, dias):
    from datetime import date, timedelta as td
    from models import db, DiaActividad
    with app.app_context():
        for hace in range(dias):
            db.session.add(DiaActividad(fecha=date.today() - td(days=hace)))
        db.session.commit()


def test_racha_sin_record_no_avisa(app_abierta):
    _sembrar_racha(app_abierta, 1)  # 1 día: por debajo del mínimo (2) para avisar
    with patch("winotify.Notification") as MockNotification:
        escritorio._avisar_racha_record(app_abierta)
        MockNotification.assert_not_called()


def test_racha_que_iguala_el_record_avisa(app_abierta):
    _sembrar_racha(app_abierta, 3)  # racha actual == récord (solo tiene esta racha)
    instancia = MagicMock()
    with patch("winotify.Notification", return_value=instancia) as MockNotification:
        escritorio._avisar_racha_record(app_abierta)
    MockNotification.assert_called_once()
    assert "3 días" in MockNotification.call_args.kwargs["msg"]
    instancia.show.assert_called_once()


def test_racha_activa_pero_por_debajo_del_record_no_avisa(app_abierta):
    from datetime import date, timedelta
    from models import db, DiaActividad
    with app_abierta.app_context():
        # récord viejo de 5 días, roto, más la racha actual de 2
        for hace in (10, 11, 12, 13, 14):
            db.session.add(DiaActividad(fecha=date.today() - timedelta(days=hace)))
        for hace in (0, 1):
            db.session.add(DiaActividad(fecha=date.today() - timedelta(days=hace)))
        db.session.commit()

    with patch("winotify.Notification") as MockNotification:
        escritorio._avisar_racha_record(app_abierta)
        MockNotification.assert_not_called()
