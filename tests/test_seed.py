from models import db, Asignatura


def test_seed_no_duplica_al_ejecutarse_dos_veces(app_vacia):
    from seed import poblar_datos_iniciales

    with app_vacia.app_context():
        poblar_datos_iniciales()
        total_primera_vez = Asignatura.query.count()
        assert total_primera_vez == 54

        poblar_datos_iniciales()
        total_segunda_vez = Asignatura.query.count()

        assert total_segunda_vez == total_primera_vez


def test_seed_no_sobrescribe_datos_editados_a_mano(app_vacia):
    from seed import poblar_datos_iniciales

    with app_vacia.app_context():
        poblar_datos_iniciales()

        asignatura = Asignatura.query.filter_by(nombre="Diseño Digital").first()
        asignatura.notas = "nota manual que no debe desaparecer"
        asignatura.despacho_profesor = "Edificio X, 3ª planta"
        db.session.commit()

        poblar_datos_iniciales()  # segunda pasada

        asignatura_recargada = Asignatura.query.filter_by(nombre="Diseño Digital").first()
        assert asignatura_recargada.notas == "nota manual que no debe desaparecer"
        assert asignatura_recargada.despacho_profesor == "Edificio X, 3ª planta"


def test_seed_no_elimina_registros_existentes(app_vacia):
    from seed import poblar_datos_iniciales

    with app_vacia.app_context():
        poblar_datos_iniciales()
        ids_antes = {a.id for a in Asignatura.query.all()}

        poblar_datos_iniciales()
        ids_despues = {a.id for a in Asignatura.query.all()}

        assert ids_antes == ids_despues
