"""add TTS engine and repetition options

Revision ID: c3d4e5f6a7b8
Revises: a9b8c7d6e5f4
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('voice_call_config') as batch_op:
        batch_op.add_column(sa.Column('tts_engine', sa.String(), nullable=False, server_default='piper'))
        batch_op.add_column(sa.Column('tts_model', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('repeat_count', sa.Integer(), nullable=False, server_default='3'))
        batch_op.add_column(sa.Column('repeat_pause_seconds', sa.Float(), nullable=False, server_default='0.8'))


def downgrade() -> None:
    with op.batch_alter_table('voice_call_config') as batch_op:
        batch_op.drop_column('repeat_pause_seconds')
        batch_op.drop_column('repeat_count')
        batch_op.drop_column('tts_model')
        batch_op.drop_column('tts_engine')
