"""orden en componente_evaluacion (reordenar componentes)

Revision ID: a1c3e5f7b9d2
Revises: 7572e1b913a6
Create Date: 2026-09-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1c3e5f7b9d2'
down_revision = '7572e1b913a6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('componente_evaluacion', schema=None) as batch_op:
        batch_op.add_column(sa.Column('orden', sa.Integer(), nullable=False, server_default='0'))
    # Conserva el orden de siempre (por id) para lo ya existente.
    op.execute("UPDATE componente_evaluacion SET orden = id")


def downgrade():
    with op.batch_alter_table('componente_evaluacion', schema=None) as batch_op:
        batch_op.drop_column('orden')
