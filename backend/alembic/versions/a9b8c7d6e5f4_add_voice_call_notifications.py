"""add voice call notifications

Revision ID: a9b8c7d6e5f4
Revises: f7a8b9c0d1e2
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('services') as batch_op:
        batch_op.add_column(
            sa.Column('voice_call', sa.Boolean(), nullable=False, server_default='0')
        )
        batch_op.add_column(sa.Column('voice_alerted_at', sa.DateTime(), nullable=True))

    op.create_table(
        'voice_call_config',
        sa.Column('singleton_id', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('destination', sa.String(), nullable=True),
        sa.Column('delay_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('sip_number', sa.String(), nullable=True),
        sa.Column('sip_auth_username', sa.String(), nullable=True),
        sa.Column('sip_password', sa.String(), nullable=True),
        sa.Column('sip_registrar', sa.String(), nullable=True),
        sa.Column('sip_proxy', sa.String(), nullable=True),
        sa.Column('dns_server', sa.String(), nullable=True),
        sa.Column('tts_language', sa.String(), nullable=False, server_default='de'),
        sa.Column('message_template', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('singleton_id'),
    )


def downgrade() -> None:
    op.drop_table('voice_call_config')
    with op.batch_alter_table('services') as batch_op:
        batch_op.drop_column('voice_alerted_at')
        batch_op.drop_column('voice_call')
