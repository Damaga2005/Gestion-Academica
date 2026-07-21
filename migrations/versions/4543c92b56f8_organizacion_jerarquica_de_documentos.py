"""organizacion jerarquica de documentos

Revision ID: 4543c92b56f8
Revises: fbc3c60c71ff
Create Date: 2026-07-20 23:11:18.256094

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4543c92b56f8'
down_revision = 'fbc3c60c71ff'
branch_labels = None
depends_on = None


FK_DOCUMENTO_GRUPO = "fk_documento_grupo_documento_id"

MAPA_APARTADO_A_CATEGORIA = {
    "teoría": "teoria",
    "exámenes": "examenes",
    "laboratorio": "laboratorios",
}


def upgrade():
    """Reentrante, igual que las migraciones anteriores de esta app: en SQLite el DDL
    hace auto-commit, así que cada paso comprueba antes de aplicarse por si el proceso
    murió a medias en un intento anterior."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "grupo_documento" not in inspector.get_table_names():
        op.create_table('grupo_documento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asignatura_id', sa.Integer(), nullable=False),
        sa.Column('categoria', sa.String(length=20), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['asignatura_id'], ['asignatura.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asignatura_id', 'categoria', 'nombre', name='uq_grupo_documento_asig_cat_nombre')
        )

    columnas_documento = {c["name"] for c in inspector.get_columns("documento")}
    columnas_a_anadir = [
        (nombre, tipo) for nombre, tipo in (
            ("categoria", sa.String(length=20)),
            ("grupo_documento_id", sa.Integer()),
            ("tamano_bytes", sa.Integer()),
        ) if nombre not in columnas_documento
    ]
    apartado_id_es_nullable = next(
        (c["nullable"] for c in inspector.get_columns("documento") if c["name"] == "apartado_id"), True
    )
    fk_grupo_existe = any(
        fk["constrained_columns"] == ["grupo_documento_id"] for fk in inspector.get_foreign_keys("documento")
    )

    if columnas_a_anadir or not apartado_id_es_nullable or not fk_grupo_existe:
        with op.batch_alter_table('documento', schema=None) as batch_op:
            for nombre, tipo in columnas_a_anadir:
                batch_op.add_column(sa.Column(nombre, tipo, nullable=True))
            if not apartado_id_es_nullable:
                batch_op.alter_column('apartado_id', existing_type=sa.INTEGER(), nullable=True)
            if not fk_grupo_existe:
                batch_op.create_foreign_key(FK_DOCUMENTO_GRUPO, 'grupo_documento', ['grupo_documento_id'], ['id'])

    _migrar_documentos_a_categorias()


def _migrar_documentos_a_categorias():
    """
    Backfill (spec punto 11: "mantener todos los documentos existentes"): a cada
    Documento que todavía no tenga `categoria` se le asigna una a partir de su
    Apartado de origen.

    - Apartados de partida (Teoría/Exámenes/Laboratorio): mapeo directo a la
      categoría fija correspondiente, sin subgrupo (grupo_documento_id=NULL, se ve
      como "Sin clasificar" dentro de esa categoría).
    - Apartados personalizados (creados a mano, p. ej. "Prácticas"): para no perder
      esa organización se preservan como subgrupo dentro de la categoría "Otros",
      con su mismo nombre.
    - Documento sin apartado resoluble (no debería pasar, pero por si acaso): cae en
      "Otros" sin subgrupo, mejor que dejarlo sin categoría.

    Reentrante: solo toca documentos con categoria IS NULL, así que un reintento no
    vuelve a crear grupos duplicados ni pisa clasificaciones ya migradas.
    """
    bind = op.get_bind()

    documento_t = sa.table(
        "documento",
        sa.column("id", sa.Integer), sa.column("apartado_id", sa.Integer),
        sa.column("categoria", sa.String), sa.column("grupo_documento_id", sa.Integer),
    )
    apartado_t = sa.table(
        "apartado",
        sa.column("id", sa.Integer), sa.column("asignatura_id", sa.Integer), sa.column("nombre", sa.String),
    )
    grupo_t = sa.table(
        "grupo_documento",
        sa.column("id", sa.Integer), sa.column("asignatura_id", sa.Integer),
        sa.column("categoria", sa.String), sa.column("nombre", sa.String), sa.column("orden", sa.Integer),
        sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )

    pendientes = bind.execute(
        sa.select(documento_t.c.id, documento_t.c.apartado_id).where(documento_t.c.categoria.is_(None))
    ).fetchall()

    cache_grupo_otros = {}  # (asignatura_id, nombre_apartado) -> grupo_id ya creado en esta pasada

    for doc_id, apartado_id in pendientes:
        apartado = None
        if apartado_id is not None:
            apartado = bind.execute(
                sa.select(apartado_t.c.asignatura_id, apartado_t.c.nombre).where(apartado_t.c.id == apartado_id)
            ).first()

        if apartado is None:
            bind.execute(
                documento_t.update().where(documento_t.c.id == doc_id)
                .values(categoria="otros", grupo_documento_id=None)
            )
            continue

        asignatura_id, nombre_apartado = apartado
        categoria = MAPA_APARTADO_A_CATEGORIA.get(nombre_apartado.strip().lower())

        if categoria:
            bind.execute(
                documento_t.update().where(documento_t.c.id == doc_id)
                .values(categoria=categoria, grupo_documento_id=None)
            )
            continue

        clave = (asignatura_id, nombre_apartado)
        grupo_id = cache_grupo_otros.get(clave)
        if grupo_id is None:
            existente = bind.execute(
                sa.select(grupo_t.c.id).where(
                    grupo_t.c.asignatura_id == asignatura_id,
                    grupo_t.c.categoria == "otros",
                    grupo_t.c.nombre == nombre_apartado,
                )
            ).first()
            if existente:
                grupo_id = existente[0]
            else:
                from datetime import datetime
                ahora = datetime.utcnow()
                bind.execute(grupo_t.insert().values(
                    asignatura_id=asignatura_id, categoria="otros", nombre=nombre_apartado,
                    orden=0, created_at=ahora, updated_at=ahora,
                ))
                grupo_id = bind.execute(
                    sa.select(sa.func.max(grupo_t.c.id)).where(grupo_t.c.asignatura_id == asignatura_id)
                ).scalar()
            cache_grupo_otros[clave] = grupo_id

        bind.execute(
            documento_t.update().where(documento_t.c.id == doc_id)
            .values(categoria="otros", grupo_documento_id=grupo_id)
        )


def downgrade():
    with op.batch_alter_table('documento', schema=None) as batch_op:
        batch_op.drop_constraint(FK_DOCUMENTO_GRUPO, type_='foreignkey')
        batch_op.alter_column('apartado_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.drop_column('tamano_bytes')
        batch_op.drop_column('grupo_documento_id')
        batch_op.drop_column('categoria')

    op.drop_table('grupo_documento')
