import os


def test_detecta_cambio_externo_de_la_bd(client_abierto):
    app = client_abierto.application
    client_abierto.get("/anios")  # petición propia: fija la huella
    assert client_abierto.get("/bd/cambio-externo").get_json() == {"cambiado": False}

    ruta = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "", 1)
    st = os.stat(ruta)
    os.utime(ruta, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))  # "otro PC" la tocó
    assert client_abierto.get("/bd/cambio-externo").get_json() == {"cambiado": True}

    client_abierto.get("/anios")  # recargar: se acepta el estado actual
    assert client_abierto.get("/bd/cambio-externo").get_json() == {"cambiado": False}
