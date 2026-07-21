"""
Informe de asignaturas sin siglas (Fase Calendario académico y horario, punto 10).

`siglas` es nullable a propósito: la migración no inventa códigos oficiales para
asignaturas que no los tenían. Este script lista cuáles necesitan que alguien las
rellene a mano (vía PUT /asignaturas/<id> con {"siglas": "..."} o desde la ficha
de la asignatura en la interfaz), y no hace ninguna escritura por sí mismo.

Uso:
  python informe_siglas.py
"""

from app import create_app
from models import Asignatura


def informe_siglas_faltantes():
    app = create_app(auto_seed=False)
    with app.app_context():
        sin_siglas = (
            Asignatura.query.filter(Asignatura.siglas.is_(None))
            .join(Asignatura.cuatrimestre)
            .order_by(Asignatura.cuatrimestre_id, Asignatura.nombre)
            .all()
        )
        con_siglas = Asignatura.query.filter(Asignatura.siglas.isnot(None)).count()
        total = Asignatura.query.count()

        print(f"Asignaturas con siglas: {con_siglas}/{total}")
        if not sin_siglas:
            print("Todas las asignaturas tienen siglas asignadas.")
            return

        print(f"\nAsignaturas SIN siglas ({len(sin_siglas)}), agrupadas por cuatrimestre:")
        cuatrimestre_actual = None
        for a in sin_siglas:
            if a.cuatrimestre_id != cuatrimestre_actual:
                cuatrimestre_actual = a.cuatrimestre_id
                print(f"\n  Cuatrimestre {a.cuatrimestre.numero}:")
            print(f"    [id={a.id}] {a.nombre}")


if __name__ == "__main__":
    informe_siglas_faltantes()
