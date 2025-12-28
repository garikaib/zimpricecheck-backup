"""add_scheduling_fields

Revision ID: 58ad51af5479
Revises: 
Create Date: 2025-12-28 11:18:38.544685

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58ad51af5479'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns to 'sites' table
    op.add_column('sites', sa.Column('schedule_frequency', sa.String(), server_default='manual', nullable=True))
    op.add_column('sites', sa.Column('schedule_time', sa.String(), nullable=True))
    op.add_column('sites', sa.Column('schedule_days', sa.String(), nullable=True))
    op.add_column('sites', sa.Column('retention_copies', sa.Integer(), server_default='5', nullable=True))
    op.add_column('sites', sa.Column('next_run_at', sa.DateTime(), nullable=True))

    # Add columns to 'nodes' table
    op.add_column('nodes', sa.Column('max_retention_copies', sa.Integer(), server_default='10', nullable=True))
    op.add_column('nodes', sa.Column('max_concurrent_backups', sa.Integer(), server_default='2', nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # SQLite does not support drop column properly in older versions, 
    # but Alembic batch mode is needed for that. 
    # For now, simple drop (might fail on SQLite without batch)
    try:
        with op.batch_alter_table('sites') as batch_op:
            batch_op.drop_column('schedule_frequency')
            batch_op.drop_column('schedule_time')
            batch_op.drop_column('schedule_days')
            batch_op.drop_column('retention_copies')
            batch_op.drop_column('next_run_at')
        
        with op.batch_alter_table('nodes') as batch_op:
            batch_op.drop_column('max_retention_copies')
            batch_op.drop_column('max_concurrent_backups')
    except Exception as e:
        print(f"Downgrade skipped due to SQLite limitations: {e}")
