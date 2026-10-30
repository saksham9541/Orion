"""add_start_window_fields

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-10-30 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f7a8b9c0d1e'
down_revision: Union[str, Sequence[str], None] = '5e6f7a8b9c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'tasks' in existing_tables:
        task_cols = [c['name'] for c in inspector.get_columns('tasks')]
        if 'start_allowed_from' not in task_cols:
            op.add_column('tasks', sa.Column('start_allowed_from', sa.DateTime(), nullable=True))
        if 'start_allowed_until' not in task_cols:
            op.add_column('tasks', sa.Column('start_allowed_until', sa.DateTime(), nullable=True))
        if 'planned_end' not in task_cols:
            op.add_column('tasks', sa.Column('planned_end', sa.DateTime(), nullable=True))
        if 'early_tolerance_minutes' not in task_cols:
            op.add_column('tasks', sa.Column('early_tolerance_minutes', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    pass
