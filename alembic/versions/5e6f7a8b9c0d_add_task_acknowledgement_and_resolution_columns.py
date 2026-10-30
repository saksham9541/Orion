"""add_task_acknowledgement_and_resolution_columns

Revision ID: 5e6f7a8b9c0d
Revises: 016943ca4226
Create Date: 2026-10-30 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e6f7a8b9c0d'
down_revision: Union[str, Sequence[str], None] = '016943ca4226'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Update tasks table with acknowledgement columns
    if 'tasks' in existing_tables:
        task_cols = [c['name'] for c in inspector.get_columns('tasks')]
        if 'acknowledged_by' not in task_cols:
            op.add_column('tasks', sa.Column('acknowledged_by', sa.String(length=100), nullable=True))
        if 'acknowledged_at' not in task_cols:
            op.add_column('tasks', sa.Column('acknowledged_at', sa.DateTime(), nullable=True))
        if 'declined_by' not in task_cols:
            op.add_column('tasks', sa.Column('declined_by', sa.String(length=100), nullable=True))
        if 'declined_at' not in task_cols:
            op.add_column('tasks', sa.Column('declined_at', sa.DateTime(), nullable=True))
        if 'decline_reason' not in task_cols:
            op.add_column('tasks', sa.Column('decline_reason', sa.Text(), nullable=True))
        if 'awaiting_acknowledgement' not in task_cols:
            op.add_column('tasks', sa.Column('awaiting_acknowledgement', sa.Boolean(), nullable=True, server_default=sa.false()))

    # 2. Update notifications table with resolution columns
    if 'notifications' in existing_tables:
        notif_cols = [c['name'] for c in inspector.get_columns('notifications')]
        if 'resolved_at' not in notif_cols:
            op.add_column('notifications', sa.Column('resolved_at', sa.DateTime(), nullable=True))
        if 'resolved_by' not in notif_cols:
            op.add_column('notifications', sa.Column('resolved_by', sa.String(length=100), nullable=True))
        if 'action_taken' not in notif_cols:
            op.add_column('notifications', sa.Column('action_taken', sa.String(length=50), nullable=True))


def downgrade() -> None:
    pass
