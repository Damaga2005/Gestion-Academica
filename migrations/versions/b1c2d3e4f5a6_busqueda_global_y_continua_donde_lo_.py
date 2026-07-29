"""busqueda global y continua donde lo dejaste

Revision ID: b1c2d3e4f5a6
Revises: d7b267f6cfa5
Create Date: 2026-07-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'd7b267f6cfa5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('documento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('porcentaje_leido', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('zoom_nivel', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('modo_visualizacion', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('scroll_vertical', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('fecha_primera_apertura', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('fecha_ultima_apertura', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column(
            'tiempo_total_lectura_segundos', sa.Integer(), nullable=False, server_default='0'
        ))
        batch_op.add_column(sa.Column('numero_sesiones', sa.Integer(), nullable=False, server_default='0'))

    op.create_table(
        'busqueda_favorito',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo_entidad', sa.String(length=20), nullable=False),
        sa.Column('entidad_id', sa.Integer(), nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tipo_entidad', 'entidad_id', name='uq_favorito_entidad'),
    )

    op.create_table(
        'busqueda_reciente',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo_entidad', sa.String(length=20), nullable=False),
        sa.Column('entidad_id', sa.Integer(), nullable=False),
        sa.Column('etiqueta_mostrada', sa.String(length=300), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('fecha_acceso', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('busqueda_reciente')
    op.drop_table('busqueda_favorito')

    with op.batch_alter_table('documento', schema=None) as batch_op:
        batch_op.drop_column('numero_sesiones')
        batch_op.drop_column('tiempo_total_lectura_segundos')
        batch_op.drop_column('fecha_ultima_apertura')
        batch_op.drop_column('fecha_primera_apertura')
        batch_op.drop_column('scroll_vertical')
        batch_op.drop_column('modo_visualizacion')
        batch_op.drop_column('zoom_nivel')
        batch_op.drop_column('porcentaje_leido')
