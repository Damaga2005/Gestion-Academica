"""tarea_evento: documento_id para integracion con el visor pdf

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tarea_evento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('documento_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_tarea_evento_documento_id', 'documento', ['documento_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('tarea_evento', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tarea_evento_documento_id', type_='foreignkey')
        batch_op.drop_column('documento_id')
