"""add_site_url_to_service

Revision ID: a1b2c3d4e5f6
Revises: c52e5e0ecf6d
Create Date: 2026-03-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c52e5e0ecf6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('services', sa.Column('site_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('services', 'site_url')
