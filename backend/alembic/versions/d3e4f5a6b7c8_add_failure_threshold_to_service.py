"""add_failure_threshold_to_service

Revision ID: d3e4f5a6b7c8
Revises: b1c2d3e4f5a6
Create Date: 2026-03-10

Adds failure_threshold (integer, default 2) to the services table.
Controls how many consecutive failed checks must occur before a service
transitions to outage.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default required: SQLite cannot add a NOT NULL column without one.
    op.add_column(
        'services',
        sa.Column('failure_threshold', sa.Integer(), nullable=False, server_default='2'),
    )


def downgrade() -> None:
    op.drop_column('services', 'failure_threshold')
