"""store last check detail and add a call duration cap

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('services') as batch_op:
        batch_op.add_column(sa.Column('last_detail', sa.Text(), nullable=True))
    with op.batch_alter_table('voice_call_config') as batch_op:
        batch_op.add_column(
            sa.Column('max_call_seconds', sa.Integer(), nullable=False, server_default='600')
        )


def downgrade() -> None:
    with op.batch_alter_table('voice_call_config') as batch_op:
        batch_op.drop_column('max_call_seconds')
    with op.batch_alter_table('services') as batch_op:
        batch_op.drop_column('last_detail')
