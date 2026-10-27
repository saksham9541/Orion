"""add_notifications_table

Revision ID: 2b3c4d5e6f7a
Revises: 1f2ce0269a3f
Create Date: 2026-10-27 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2b3c4d5e6f7a'
down_revision: Union[str, Sequence[str], None] = '1f2ce0269a3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Add columns to tasks if not present
    if 'tasks' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('tasks')}
        if 'department_designated' not in existing_cols:
            op.add_column('tasks', sa.Column('department_designated', sa.String(length=50), nullable=True))
        if 'created_by' not in existing_cols:
            op.add_column('tasks', sa.Column('created_by', sa.String(length=100), nullable=True))
        if 'created_by_department' not in existing_cols:
            op.add_column('tasks', sa.Column('created_by_department', sa.String(length=50), nullable=True))
        if 'created_at' not in existing_cols:
            op.add_column('tasks', sa.Column('created_at', sa.DateTime(), nullable=True))

    # 2. Create notifications table if not present
    if 'notifications' not in existing_tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('issue_id', sa.String(), nullable=True),
            sa.Column('recipient_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('type', sa.String(length=50), nullable=False, server_default='ISSUE_RAISED'),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('severity', sa.String(length=20), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_notifications_recipient_user_id', 'notifications', ['recipient_user_id'])
        op.create_index('ix_notifications_issue_id', 'notifications', ['issue_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'notifications' in existing_tables:
        op.drop_table('notifications')

    if 'tasks' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('tasks')}
        if 'department_designated' in existing_cols:
            op.drop_column('tasks', 'department_designated')
        if 'created_by' in existing_cols:
            op.drop_column('tasks', 'created_by')
        if 'created_by_department' in existing_cols:
            op.drop_column('tasks', 'created_by_department')
        if 'created_at' in existing_cols:
            op.drop_column('tasks', 'created_at')
