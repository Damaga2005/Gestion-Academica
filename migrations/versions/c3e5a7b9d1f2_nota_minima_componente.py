"""nota_minima en componente_evaluacion

Revision ID: c3e5a7b9d1f2
Revises: b2d4f6a8c0e1
Create Date: 2026-09-19 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3e5a7b9d1f2'
down_revision = 'b2d4f6a8c0e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('componente_evaluacion', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nota_minima', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('componente_evaluacion', schema=None) as batch_op:
        batch_op.drop_column('nota_minima')
