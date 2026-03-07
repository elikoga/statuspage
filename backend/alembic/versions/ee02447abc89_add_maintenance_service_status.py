"""add_offline_service_status

Revision ID: ee02447abc89
Revises: 492f3e974bf2
Create Date: 2026-03-07

SQLite stores the ServiceStatus enum as plain VARCHAR — no CHECK constraint
exists in the schema, so adding a new enum value requires no DDL change.
This migration exists solely to advance the Alembic version head.

New value: 'offline' — intentionally shut down, not broken.
The health-check loop skips services with this status entirely.
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'ee02447abc89'
down_revision: Union[str, None] = '492f3e974bf2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No DDL needed: SQLite status column is VARCHAR with no CHECK constraint.
    pass


def downgrade() -> None:
    pass
