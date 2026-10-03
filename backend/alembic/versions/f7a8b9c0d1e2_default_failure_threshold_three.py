"""default_failure_threshold_three

Revision ID: f7a8b9c0d1e2
Revises: e1f2a3b4c5d6
Create Date: 2026-10-03

Raises the server-side default of services.failure_threshold from 2 to 3, so
new services need three consecutive failed checks (30s at the default 10s
interval) before transitioning to outage. Existing rows keep their configured
value.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite cannot alter a column default in place; batch mode rebuilds the table.
    with op.batch_alter_table('services') as batch_op:
        batch_op.alter_column(
            'failure_threshold',
            existing_type=sa.Integer(),
            nullable=False,
            server_default='3',
        )


def downgrade() -> None:
    with op.batch_alter_table('services') as batch_op:
        batch_op.alter_column(
            'failure_threshold',
            existing_type=sa.Integer(),
            nullable=False,
            server_default='2',
        )
