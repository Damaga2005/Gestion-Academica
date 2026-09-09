from datetime import date, timedelta

from flask import Blueprint, jsonify

from models import Asignatura, Cuatrimestre, HorarioClase, TareaEvento

linea_tiempo_bp = Blueprint("linea_tiempo", __name__)

# Ventana de respaldo cuando el cuatrimestre "actual" no tiene ningún dato con fecha
# todavía (horario/tareas sin rellenar): sin esto no habría nada que dibujar.
_DIAS_ANTES_RESPALDO = 7
_DIAS_DESPUES_RESPALDO = 90


@linea_tiempo_bp.get("/linea-tiempo")
def obtener_linea_tiempo():
    cuatrimestres_actuales = Cuatrimestre.query.filter_by(estado="actual").all()
    asignaturas = (
        Asignatura.query.filter(Asignatura.cuatrimestre_id.in_([c.id for c in cuatrimestres_actuales]))
        .order_by(Asignatura.nombre)
        .all()
        if cuatrimestres_actuales else []
    )

    filas = []
    fechas = []
    for a in asignaturas:
        horarios = HorarioClase.query.filter_by(asignatura_id=a.id).all()
        eventos = TareaEvento.query.filter_by(asignatura_id=a.id).all()
        if not horarios and not eventos:
            continue  # asignatura sin nada temporal todavía: no aporta a la línea de tiempo

        barra = None
        if horarios:
            inicio = min(h.fecha_inicio for h in horarios)
            fin = max(h.fecha_fin for h in horarios)
            barra = {"inicio": inicio.isoformat(), "fin": fin.isoformat()}
            fechas += [inicio, fin]

        marcadores = [
            {"id": t.id, "titulo": t.titulo, "fecha": t.fecha.isoformat(), "tipo": t.tipo, "completada": t.completada}
            for t in sorted(eventos, key=lambda t: t.fecha)
        ]
        fechas += [t.fecha for t in eventos]

        filas.append({
            "asignatura_id": a.id,
            "nombre": a.nombre,
            "siglas": a.siglas,
            "barra": barra,
            "marcadores": marcadores,
        })

    hoy = date.today()
    inicio_rango = min(fechas) if fechas else hoy - timedelta(days=_DIAS_ANTES_RESPALDO)
    fin_rango = max(fechas) if fechas else hoy + timedelta(days=_DIAS_DESPUES_RESPALDO)
    # Un poco de margen a cada lado para que nada quede pegado al borde.
    inicio_rango -= timedelta(days=3)
    fin_rango += timedelta(days=3)

    return jsonify({
        "rango": {"inicio": inicio_rango.isoformat(), "fin": fin_rango.isoformat()},
        "hoy": hoy.isoformat(),
        "filas": filas,
    })
