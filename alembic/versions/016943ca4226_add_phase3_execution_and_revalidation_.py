"""add_phase3_execution_and_revalidation_tables

Revision ID: 016943ca4226
Revises: 4d5e6f7a8b9c
Create Date: 2026-10-30 15:51:20.081067

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '016943ca4226'
down_revision: Union[str, Sequence[str], None] = '4d5e6f7a8b9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Update tasks table with execution columns
    if 'tasks' in existing_tables:
        task_cols = [c['name'] for c in inspector.get_columns('tasks')]
        if 'actual_start' not in task_cols:
            op.add_column('tasks', sa.Column('actual_start', sa.DateTime(), nullable=True))
        if 'actual_end' not in task_cols:
            op.add_column('tasks', sa.Column('actual_end', sa.DateTime(), nullable=True))
        if 'execution_outcome' not in task_cols:
            op.add_column('tasks', sa.Column('execution_outcome', sa.String(length=50), nullable=True))
        if 'execution_notes' not in task_cols:
            op.add_column('tasks', sa.Column('execution_notes', sa.Text(), nullable=True))
        if 'abort_reason_code' not in task_cols:
            op.add_column('tasks', sa.Column('abort_reason_code', sa.String(length=50), nullable=True))
        if 'suspend_reason_code' not in task_cols:
            op.add_column('tasks', sa.Column('suspend_reason_code', sa.String(length=50), nullable=True))
        if 'pre_start_check_passed' not in task_cols:
            op.add_column('tasks', sa.Column('pre_start_check_passed', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        if 'pre_start_check_by' not in task_cols:
            op.add_column('tasks', sa.Column('pre_start_check_by', sa.String(length=100), nullable=True))
        if 'pre_start_check_at' not in task_cols:
            op.add_column('tasks', sa.Column('pre_start_check_at', sa.DateTime(), nullable=True))
        if 'overrun_detected_at' not in task_cols:
            op.add_column('tasks', sa.Column('overrun_detected_at', sa.DateTime(), nullable=True))

    # 2. Create revalidation_results table
    if 'revalidation_results' not in existing_tables:
        op.create_table(
            'revalidation_results',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('task_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('window_id', sa.String(length=64), nullable=True),
            sa.Column('block_section_id', sa.String(length=64), nullable=True),
            sa.Column('checked_at', sa.DateTime(), nullable=False),
            sa.Column('horizon', sa.String(length=20), nullable=True),
            sa.Column('is_valid', sa.Boolean(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('confidence', sa.String(length=16), nullable=False),
            sa.Column('stale_status', sa.Boolean(), nullable=True, server_default=sa.text('0')),
            sa.Column('status_age_hours', sa.Float(), nullable=True, server_default=sa.text('0.0')),
            sa.Column('has_conflict', sa.Boolean(), nullable=True, server_default=sa.text('0')),
            sa.Column('affected_trains', sa.JSON(), nullable=True),
            sa.Column('bounding_trains', sa.JSON(), nullable=True),
            sa.Column('next_best_start', sa.String(length=16), nullable=True),
            sa.Column('reasons', sa.JSON(), nullable=True),
            sa.Column('triggered_by', sa.String(length=32), nullable=True, server_default='USER'),
        )

    # 3. Create task_transition_audits table
    if 'task_transition_audits' not in existing_tables:
        op.create_table(
            'task_transition_audits',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('task_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('from_status', sa.String(length=32), nullable=False),
            sa.Column('to_status', sa.String(length=32), nullable=False),
            sa.Column('changed_by_user_id', sa.String(length=64), nullable=True),
            sa.Column('changed_by_role', sa.String(length=32), nullable=True),
            sa.Column('changed_by_department', sa.String(length=32), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('reason_code', sa.String(length=64), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('details', sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'task_transition_audits' in existing_tables:
        op.drop_table('task_transition_audits')

    if 'revalidation_results' in existing_tables:
        op.drop_table('revalidation_results')

    if 'tasks' in existing_tables:
        task_cols = [c['name'] for c in inspector.get_columns('tasks')]
        for col in [
            'overrun_detected_at', 'pre_start_check_at', 'pre_start_check_by',
            'pre_start_check_passed', 'suspend_reason_code', 'abort_reason_code',
            'execution_notes', 'execution_outcome', 'actual_end', 'actual_start'
        ]:
            if col in task_cols:
                op.drop_column('tasks', col)
