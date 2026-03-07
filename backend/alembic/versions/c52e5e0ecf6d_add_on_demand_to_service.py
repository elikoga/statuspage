"""add_on_demand_to_service

Revision ID: c52e5e0ecf6d
Revises: ee02447abc89
Create Date: 2026-03-07

on_demand=True marks a service whose downtime is expected; failed health
checks keep it 'offline' rather than escalating to 'outage'.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c52e5e0ecf6d'
down_revision: Union[str, None] = 'ee02447abc89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default required: SQLite cannot add a NOT NULL column without one.
    op.add_column(
        'services',
        sa.Column('on_demand', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('services', 'on_demand')
