"""Corrige un error de mapeo: los 5 examenes 'Parcial_*.jpg' de la carpeta OneDrive
CIAF se importaron bajo la asignatura 27 (ICAF = Introducción a los Circuitos de Alta
Frecuencia), pero CIAF es en realidad el código oficial de la asignatura 34 (Circuitos
de Alta Frecuencia), una asignatura distinta. Los mueve de 27 a 34."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def ejecutar(database_uri=None, documentos_dir=None):
    from app import create_app
    from models import db, Asignatura, GrupoDocumento, Documento
    from utils import carpeta_categoria, carpeta_grupo, ruta_absoluta, nombre_archivo_disponible
    import shutil

    app = create_app(auto_seed=False, database_uri=database_uri, documentos_dir=documentos_dir)
    with app.app_context():
        origen_asig = Asignatura.query.get(27)
        destino_asig = Asignatura.query.get(34)
        if origen_asig is None or destino_asig is None:
            print("AVISO: asignatura 27 o 34 no existe")
            return

        documentos = Documento.query.filter_by(asignatura_id=27, categoria="examenes").filter(
            Documento.nombre_archivo.like("Parcial_%.jpg")
        ).all()
        print(f"Moviendo {len(documentos)} documentos de asignatura 27 -> 34")
        if not documentos:
            return

        grupo_destino = GrupoDocumento.query.filter_by(
            asignatura_id=34, categoria="examenes", nombre="Parciales"
        ).first()
        if not grupo_destino:
            grupo_destino = GrupoDocumento(asignatura_id=34, categoria="examenes", nombre="Parciales", orden=0)
            db.session.add(grupo_destino)
            db.session.flush()

        carpeta_destino = carpeta_grupo(destino_asig, grupo_destino)
        os.makedirs(carpeta_destino, exist_ok=True)

        grupo_origen_id = documentos[0].grupo_documento_id
        for doc in documentos:
            origen = ruta_absoluta(doc.ruta_local)
            nombre_final = nombre_archivo_disponible(carpeta_destino, doc.nombre_archivo)
            destino = os.path.join(carpeta_destino, nombre_final)
            if os.path.exists(origen):
                shutil.move(origen, destino)
            doc.asignatura_id = 34
            doc.grupo_documento_id = grupo_destino.id
            doc.nombre_archivo = nombre_final
            doc.ruta_local = os.path.relpath(destino, app.config["DOCUMENTOS_DIR"]).replace(os.sep, "/")

        db.session.flush()
        if grupo_origen_id:
            grupo_origen = GrupoDocumento.query.get(grupo_origen_id)
            if grupo_origen and not grupo_origen.documentos:
                carpeta_origen = carpeta_grupo(origen_asig, grupo_origen)
                db.session.delete(grupo_origen)
                db.session.flush()
                if os.path.isdir(carpeta_origen):
                    shutil.rmtree(carpeta_origen, ignore_errors=True)

        db.session.commit()
        print("Hecho.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "dev"
    base = os.path.dirname(os.path.abspath(__file__))
    if target == "dist":
        ejecutar(
            database_uri=f"sqlite:///{os.path.join(base, 'dist', 'academico.db')}",
            documentos_dir=os.path.join(base, "dist", "documentos"),
        )
    else:
        ejecutar()
