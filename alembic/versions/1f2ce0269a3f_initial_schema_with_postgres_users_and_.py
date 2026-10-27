"""initial_schema_with_postgres_users_and_source

Revision ID: 1f2ce0269a3f
Revises: 
Create Date: 2026-10-27 13:50:54.735197

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '1f2ce0269a3f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON_TYPE = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. tasks
    if 'tasks' not in existing_tables:
        op.create_table(
            'tasks',
            sa.Column('task_id', sa.String(), primary_key=True),
            sa.Column('source_system', sa.String(), nullable=True),
            sa.Column('source_record_id', sa.String(), nullable=True),
            sa.Column('source', sa.String(length=20), nullable=False, server_default='synthetic'),
            sa.Column('department', sa.String(), nullable=True),
            sa.Column('asset_type', sa.String(), nullable=True),
            sa.Column('asset_id', sa.String(), nullable=True),
            sa.Column('defect_category', sa.String(), nullable=True),
            sa.Column('raw_severity', sa.String(), nullable=True),
            sa.Column('corridor_id', sa.String(), nullable=True),
            sa.Column('section_id', sa.String(), nullable=True),
            sa.Column('km_location', sa.Float(), nullable=True),
            sa.Column('km_start', sa.Float(), nullable=True),
            sa.Column('km_end', sa.Float(), nullable=True),
            sa.Column('reported_date', sa.Date(), nullable=True),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('days_overdue', sa.Integer(), nullable=True),
            sa.Column('inspector_remarks', sa.Text(), nullable=True),
            sa.Column('is_safety_critical', sa.Boolean(), nullable=True),
            sa.Column('requires_power_block', sa.Boolean(), nullable=True),
            sa.Column('requires_traffic_block', sa.Boolean(), nullable=True),
            sa.Column('crew_size_required', sa.Integer(), nullable=True),
            sa.Column('tools_special', JSON_TYPE, nullable=True),
            sa.Column('asset_age_years', sa.Float(), nullable=True),
            sa.Column('historical_failure_count', sa.Integer(), nullable=True),
            sa.Column('last_maintenance_date', sa.Date(), nullable=True),
            sa.Column('ml_criticality_score', sa.Float(), nullable=True),
            sa.Column('ml_predicted_severity', sa.String(), nullable=True),
            sa.Column('ml_predicted_duration_hours', sa.Float(), nullable=True),
            sa.Column('ml_duration_confidence_lower', sa.Float(), nullable=True),
            sa.Column('ml_duration_confidence_upper', sa.Float(), nullable=True),
            sa.Column('ml_shap_values', JSON_TYPE, nullable=True),
            sa.Column('estimated_duration_hours', sa.Float(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('assigned_block_id', sa.String(), nullable=True),
            sa.Column('deferred_count', sa.Integer(), nullable=True),
        )
        op.create_index(op.f('ix_tasks_source'), 'tasks', ['source'], unique=False)
    else:
        # If tasks exists, ensure 'source' column is present
        columns = [c['name'] for c in inspector.get_columns('tasks')]
        if 'source' not in columns:
            op.add_column('tasks', sa.Column('source', sa.String(length=20), nullable=False, server_default='synthetic'))
            op.create_index(op.f('ix_tasks_source'), 'tasks', ['source'], unique=False)

    # 2. plans
    if 'plans' not in existing_tables:
        op.create_table(
            'plans',
            sa.Column('plan_id', sa.String(), primary_key=True),
            sa.Column('source', sa.String(length=20), nullable=False, server_default='synthetic'),
            sa.Column('horizon', sa.String(), nullable=True),
            sa.Column('start_date', sa.Date(), nullable=True),
            sa.Column('end_date', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('scheduled_blocks', JSON_TYPE, nullable=True),
            sa.Column('total_tasks_scheduled', sa.Integer(), nullable=True),
            sa.Column('total_tasks_deferred', sa.Integer(), nullable=True),
            sa.Column('total_block_hours', sa.Float(), nullable=True),
            sa.Column('total_merge_savings_hours', sa.Float(), nullable=True),
            sa.Column('total_trains_affected', sa.Integer(), nullable=True),
            sa.Column('sla_compliance_pct', sa.Float(), nullable=True),
            sa.Column('departments_summary', JSON_TYPE, nullable=True),
            sa.Column('deferred_task_ids', JSON_TYPE, nullable=True),
            sa.Column('escalated_task_ids', JSON_TYPE, nullable=True),
            sa.Column('solver_status', sa.String(), nullable=True),
            sa.Column('solve_time_ms', sa.Float(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('approved_by', sa.String(), nullable=True),
            sa.Column('override_log', JSON_TYPE, nullable=True),
        )
        op.create_index(op.f('ix_plans_source'), 'plans', ['source'], unique=False)
    else:
        columns = [c['name'] for c in inspector.get_columns('plans')]
        if 'source' not in columns:
            op.add_column('plans', sa.Column('source', sa.String(length=20), nullable=False, server_default='synthetic'))
            op.create_index(op.f('ix_plans_source'), 'plans', ['source'], unique=False)

    # 3. corridors
    if 'corridors' not in existing_tables:
        op.create_table(
            'corridors',
            sa.Column('corridor_id', sa.String(), primary_key=True),
            sa.Column('source', sa.String(length=20), nullable=False, server_default='synthetic'),
            sa.Column('name', sa.String(), nullable=True),
            sa.Column('division', sa.String(), nullable=True),
            sa.Column('zone', sa.String(), nullable=True),
            sa.Column('sections', JSON_TYPE, nullable=True),
            sa.Column('total_length_km', sa.Float(), nullable=True),
            sa.Column('is_rajdhani_route', sa.Boolean(), nullable=True),
        )
        op.create_index(op.f('ix_corridors_source'), 'corridors', ['source'], unique=False)
    else:
        columns = [c['name'] for c in inspector.get_columns('corridors')]
        if 'source' not in columns:
            op.add_column('corridors', sa.Column('source', sa.String(length=20), nullable=False, server_default='synthetic'))
            op.create_index(op.f('ix_corridors_source'), 'corridors', ['source'], unique=False)

    # 4. alerts
    if 'alerts' not in existing_tables:
        op.create_table(
            'alerts',
            sa.Column('warning_id', sa.String(), primary_key=True),
            sa.Column('corridor_id', sa.String(), nullable=True),
            sa.Column('section_id', sa.String(), nullable=True),
            sa.Column('asset_type', sa.String(), nullable=True),
            sa.Column('risk_level', sa.String(), nullable=True),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('trend_data', JSON_TYPE, nullable=True),
            sa.Column('recommended_action', sa.Text(), nullable=True),
            sa.Column('estimated_failure_window_days', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    # 5. live_train_status
    if 'live_train_status' not in existing_tables:
        op.create_table(
            'live_train_status',
            sa.Column('train_number', sa.String(), primary_key=True),
            sa.Column('train_name', sa.String(), nullable=True),
            sa.Column('corridor_id', sa.String(), nullable=True),
            sa.Column('section_id', sa.String(), nullable=True),
            sa.Column('delay_minutes', sa.Float(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('last_updated', sa.DateTime(), nullable=True),
            sa.Column('source', sa.String(), nullable=True),
        )

    # 6. api_usage
    if 'api_usage' not in existing_tables:
        op.create_table(
            'api_usage',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('key_suffix', sa.String(length=10), nullable=True),
            sa.Column('year_month', sa.String(length=7), nullable=True),
            sa.Column('endpoint', sa.String(), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=True),
            sa.Column('status_code', sa.Integer(), nullable=True),
            sa.Column('success', sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_api_usage_key_suffix'), 'api_usage', ['key_suffix'], unique=False)
        op.create_index(op.f('ix_api_usage_year_month'), 'api_usage', ['year_month'], unique=False)

    # 7. api_cache
    if 'api_cache' not in existing_tables:
        op.create_table(
            'api_cache',
            sa.Column('cache_key', sa.String(), primary_key=True),
            sa.Column('endpoint', sa.String(), nullable=True),
            sa.Column('data', JSON_TYPE, nullable=True),
            sa.Column('meta', JSON_TYPE, nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
        )
        op.create_index(op.f('ix_api_cache_expires_at'), 'api_cache', ['expires_at'], unique=False)

    # 8. users
    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('department', sa.String(length=20), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_login_at', sa.DateTime(), nullable=True),
        )
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 9. login_attempts
    if 'login_attempts' not in existing_tables:
        op.create_table(
            'login_attempts',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('attempted_at', sa.DateTime(), nullable=False),
            sa.Column('success', sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_login_attempts_email'), 'login_attempts', ['email'], unique=False)


def downgrade() -> None:
    op.drop_table('login_attempts')
    op.drop_table('users')
    op.drop_table('api_cache')
    op.drop_table('api_usage')
    op.drop_table('live_train_status')
    op.drop_table('alerts')
    op.drop_table('corridors')
    op.drop_table('plans')
    op.drop_table('tasks')
