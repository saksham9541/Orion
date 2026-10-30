"""add_block_responses_table

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-10-30 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3c4d5e6f7a8b'
down_revision: Union[str, Sequence[str], None] = '2b3c4d5e6f7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'block_responses' not in existing_tables:
        op.create_table(
            'block_responses',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('plan_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('block_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('department', sa.String(length=32), nullable=False),
            sa.Column('decision', sa.String(length=16), nullable=False),
            sa.Column('counter_window_id', sa.String(length=64), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('reason_code', sa.String(length=64), nullable=True),
            sa.Column('decided_by_user_id', sa.String(length=36), nullable=False),
            sa.Column('decided_by_name', sa.String(length=128), nullable=True),
            sa.Column('decided_at', sa.DateTime(), nullable=False),
        )

    if 'live_delay_snapshots' not in existing_tables:
        op.create_table(
            'live_delay_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('snapshot_time', sa.DateTime(), nullable=False, index=True),
            sa.Column('train_no', sa.String(length=16), nullable=False, index=True),
            sa.Column('train_name', sa.String(length=128), nullable=True),
            sa.Column('current_station', sa.String(length=16), nullable=True),
            sa.Column('delay_minutes', sa.Float(), nullable=False),
            sa.Column('section_id', sa.String(length=32), nullable=True, index=True),
            sa.Column('source', sa.String(length=32), nullable=True),
        )

    if 'tasks' in existing_tables:
        task_cols = [c['name'] for c in inspector.get_columns('tasks')]
        if 'latitude' not in task_cols:
            op.add_column('tasks', sa.Column('latitude', sa.Float(), nullable=True))
        if 'longitude' not in task_cols:
            op.add_column('tasks', sa.Column('longitude', sa.Float(), nullable=True))
        if 'chainage_km' not in task_cols:
            op.add_column('tasks', sa.Column('chainage_km', sa.Float(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'block_responses' in existing_tables:
        op.drop_table('block_responses')
