"""Borra los documentos-zip de código generados por import_apuntes.py (nombre_archivo
LIKE 'Codigo_%.zip') para poder regenerarlos con una lista de extensiones ampliada."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def limpiar(database_uri=None, documentos_dir=None):
    from app import create_app
    from models import db, Documento
    from utils import ruta_absoluta

    app = create_app(auto_seed=False, database_uri=database_uri, documentos_dir=documentos_dir)
    with app.app_context():
        candidatos = Documento.query.filter(Documento.nombre_archivo.like("Codigo\\_%.zip", escape="\\")).all()
        print(f"Borrando {len(candidatos)} documentos-zip de código...")
        for doc in candidatos:
            ruta = ruta_absoluta(doc.ruta_local)
            if os.path.exists(ruta):
                os.remove(ruta)
            db.session.delete(doc)
        db.session.commit()
        print("Hecho.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "dev"
    base = os.path.dirname(os.path.abspath(__file__))
    if target == "dist":
        limpiar(
            database_uri=f"sqlite:///{os.path.join(base, 'dist', 'academico.db')}",
            documentos_dir=os.path.join(base, "dist", "documentos"),
        )
    else:
        limpiar()
