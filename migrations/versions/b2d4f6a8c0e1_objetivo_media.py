"""objetivo_media en configuracion_app

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d2
Create Date: 2026-09-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2d4f6a8c0e1'
down_revision = 'a1c3e5f7b9d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('configuracion_app', schema=None) as batch_op:
        batch_op.add_column(sa.Column('objetivo_media', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('configuracion_app', schema=None) as batch_op:
        batch_op.drop_column('objetivo_media')
