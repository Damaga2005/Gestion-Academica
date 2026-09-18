"""tabla sesion_estudio (temporizador de estudio)

Revision ID: d4f6b8c0e2a3
Revises: c3e5a7b9d1f2
Create Date: 2026-09-19 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4f6b8c0e2a3'
down_revision = 'c3e5a7b9d1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sesion_estudio',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asignatura_id', sa.Integer(), nullable=True),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('minutos', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['asignatura_id'], ['asignatura.id'], name='fk_sesion_estudio_asignatura_id'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('sesion_estudio')
