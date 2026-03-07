"""add_service_status_history

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-07

Creates service_status_history table to track per-service status transitions
over time. Each row records that a service entered a given status at started_at.

Existing services are seeded with one row each: their current status at
created_at, so the history bars show something meaningful from day one.
"""
from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'service_status_history',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('service_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_ssh_service_started',
        'service_status_history',
        ['service_id', 'started_at'],
    )

    # Seed one history row per existing service so history bars aren't blank.
    conn = op.get_bind()
    services = conn.execute(
        sa.text('SELECT id, status, created_at FROM services')
    ).fetchall()
    if services:
        conn.execute(
            sa.text(
                'INSERT INTO service_status_history (id, service_id, status, started_at) '
                'VALUES (:id, :service_id, :status, :started_at)'
            ),
            [
                {
                    'id': str(uuid.uuid4()),
                    'service_id': row[0],
                    'status': row[1],
                    'started_at': row[2],
                }
                for row in services
            ],
        )


def downgrade() -> None:
    op.drop_index('ix_ssh_service_started', table_name='service_status_history')
    op.drop_table('service_status_history')
