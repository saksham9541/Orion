"""add_block_section_columns_to_tasks

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-10-30 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d5e6f7a8b9c'
down_revision: Union[str, Sequence[str], None] = '3c4d5e6f7a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'tasks' in existing_tables:
        task_cols = [c['name'] for c in inspector.get_columns('tasks')]
        if 'block_section_id' not in task_cols:
            op.add_column('tasks', sa.Column('block_section_id', sa.String(length=64), nullable=True))
        if 'line' not in task_cols:
            op.add_column('tasks', sa.Column('line', sa.String(length=10), nullable=True, server_default='DN'))
        if 'chainage_start_km' not in task_cols:
            op.add_column('tasks', sa.Column('chainage_start_km', sa.Float(), nullable=True))
        if 'chainage_end_km' not in task_cols:
            op.add_column('tasks', sa.Column('chainage_end_km', sa.Float(), nullable=True))
        if 'requires_both_lines' not in task_cols:
            op.add_column('tasks', sa.Column('requires_both_lines', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        if 'preferred_period' not in task_cols:
            op.add_column('tasks', sa.Column('preferred_period', sa.String(length=20), nullable=True, server_default='ANY'))
        if 'reported_by' not in task_cols:
            op.add_column('tasks', sa.Column('reported_by', sa.String(length=50), nullable=True, server_default='DEPT_USER'))
        if 'history' not in task_cols:
            op.add_column('tasks', sa.Column('history', sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'tasks' in existing_tables:
        task_cols = [c['name'] for c in inspector.get_columns('tasks')]
        for col in ['history', 'reported_by', 'preferred_period', 'requires_both_lines',
                    'chainage_end_km', 'chainage_start_km', 'line', 'block_section_id']:
            if col in task_cols:
                op.drop_column('tasks', col)
