"""add_command_check_type

Revision ID: f1a2b3c4d5e6
Revises: c52e5e0ecf6d
Create Date: 2026-03-07

Adds check_type (http | command, default http) and check_command (nullable text)
to the services table.  Services with check_type='command' are checked by running
the stored shell command as a subprocess; exit 0 = operational, non-zero = outage.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default required: SQLite cannot add a NOT NULL column without one.
    op.add_column(
        'services',
        sa.Column('check_type', sa.String(), nullable=False, server_default='http'),
    )
    op.add_column(
        'services',
        sa.Column('check_command', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('services', 'check_command')
    op.drop_column('services', 'check_type')
