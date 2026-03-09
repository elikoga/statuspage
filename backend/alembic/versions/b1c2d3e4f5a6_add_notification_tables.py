"""add notification tables"""
from alembic import op
import sqlalchemy as sa

revision: str = 'b1c2d3e4f5a6'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('email_subscribers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_table('telegram_config',
        sa.Column('singleton_id', sa.String(), nullable=False),
        sa.Column('bot_token', sa.String(), nullable=True),
        sa.Column('chat_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('singleton_id'),
    )
    op.create_table('discord_config',
        sa.Column('singleton_id', sa.String(), nullable=False),
        sa.Column('bot_token', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('singleton_id'),
    )
    op.create_table('discord_destinations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('destination_type', sa.String(), nullable=False),
        sa.Column('destination_id', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('discord_destinations')
    op.drop_table('discord_config')
    op.drop_table('telegram_config')
    op.drop_table('email_subscribers')
