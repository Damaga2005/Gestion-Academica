"""Anotaciones de PDF (resaltar / subrayar / tachar / nota)

Revision ID: e1f2a3b4c5d6
Revises: c842b67f9507
Create Date: 2026-07-31

"""
from alembic import op
import sqlalchemy as sa


revision = 'e1f2a3b4c5d6'
down_revision = 'c842b67f9507'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'anotacion_pdf',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('documento_id', sa.Integer(), nullable=False),
        sa.Column('numero_pagina', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False, server_default='resaltado'),
        sa.Column('color', sa.String(length=20), nullable=False, server_default='#ffd400'),
        sa.Column('texto', sa.Text(), nullable=True),
        sa.Column('comentario', sa.Text(), nullable=True),
        sa.Column('rects', sa.Text(), nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['documento_id'], ['documento.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('anotacion_pdf', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_anotacion_pdf_documento_id'), ['documento_id'], unique=False
        )


def downgrade():
    with op.batch_alter_table('anotacion_pdf', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_anotacion_pdf_documento_id'))
    op.drop_table('anotacion_pdf')
