"""calendario academico y horario recurrente con siglas

Revision ID: fbc3c60c71ff
Revises: a3ed4ca22390
Create Date: 2026-07-20 22:08:42.876049

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fbc3c60c71ff'
down_revision = 'a3ed4ca22390'
branch_labels = None
depends_on = None


UQ_ASIGNATURA_SIGLAS = "uq_asignatura_siglas"

# Columnas nuevas de tarea_evento: (nombre, tipo SQLAlchemy)
COLUMNAS_TAREA_EVENTO = [
    ("hora_inicio", sa.Time()),
    ("hora_fin", sa.Time()),
    ("aula", sa.String(length=100)),
    ("ubicacion", sa.String(length=200)),
    ("descripcion", sa.Text()),
    ("recordatorio", sa.Integer()),
    ("link_relacionado", sa.String(length=500)),
]


def upgrade():
    """
    Reentrante a propósito, igual que la migración de esquemas de evaluación: en
    SQLite el DDL hace auto-commit, así que si el proceso muere a media migración
    (el .exe cerrándose durante el primer arranque, p. ej.) hay que poder reintentar
    sin que explote con "already exists". Cada paso comprueba antes de aplicarse.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'horario_clase' not in inspector.get_table_names():
        op.create_table('horario_clase',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asignatura_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('dia_semana', sa.Integer(), nullable=False),
        sa.Column('hora_inicio', sa.Time(), nullable=False),
        sa.Column('hora_fin', sa.Time(), nullable=False),
        sa.Column('aula', sa.String(length=100), nullable=True),
        sa.Column('fecha_inicio', sa.Date(), nullable=False),
        sa.Column('fecha_fin', sa.Date(), nullable=False),
        sa.Column('intervalo_semanas', sa.Integer(), nullable=False),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['asignatura_id'], ['asignatura.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    columnas_asignatura = {c['name'] for c in inspector.get_columns('asignatura')}
    if 'siglas' not in columnas_asignatura:
        with op.batch_alter_table('asignatura', schema=None) as batch_op:
            batch_op.add_column(sa.Column('siglas', sa.String(length=20), nullable=True))
            batch_op.create_unique_constraint(UQ_ASIGNATURA_SIGLAS, ['siglas'])

    columnas_tarea = {c['name'] for c in inspector.get_columns('tarea_evento')}
    faltantes = [(nombre, tipo) for nombre, tipo in COLUMNAS_TAREA_EVENTO if nombre not in columnas_tarea]
    if faltantes:
        with op.batch_alter_table('tarea_evento', schema=None) as batch_op:
            for nombre, tipo in faltantes:
                batch_op.add_column(sa.Column(nombre, tipo, nullable=True))


def downgrade():
    with op.batch_alter_table('tarea_evento', schema=None) as batch_op:
        for nombre, _tipo in reversed(COLUMNAS_TAREA_EVENTO):
            batch_op.drop_column(nombre)

    with op.batch_alter_table('asignatura', schema=None) as batch_op:
        batch_op.drop_constraint(UQ_ASIGNATURA_SIGLAS, type_='unique')
        batch_op.drop_column('siglas')

    op.drop_table('horario_clase')
