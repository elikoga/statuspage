"""rename_on_demand_to_muted

Revision ID: e1f2a3b4c5d6
Revises: d3e4f5a6b7c8
Create Date: 2026-03-10

Renames the services.on_demand column to services.muted.
Semantics are unchanged: muted=True suppresses notifications for a service
whose downtime is expected.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('services') as batch_op:
        batch_op.alter_column('on_demand', new_column_name='muted')


def downgrade() -> None:
    with op.batch_alter_table('services') as batch_op:
        batch_op.alter_column('muted', new_column_name='on_demand')
