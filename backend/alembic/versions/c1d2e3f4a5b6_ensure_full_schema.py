"""ensure full schema exists

Creates all tables that should have been in the original baseline migration
but were left empty and handled by create_all() instead.  Safe to run
against an existing database — every table is only created if it does not
already exist, so this migration is fully idempotent.

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _table_names()
    bind = op.get_bind()

    # ── users ────────────────────────────────────────────────────────────────
    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(255), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('email', sa.String(255), nullable=False),
            sa.Column('provider', sa.String(50), nullable=False, server_default='google'),
            sa.Column('photo_url', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('email', name='uq_users_email'),
        )

    # ── projects ─────────────────────────────────────────────────────────────
    if 'projects' not in tables:
        op.create_table(
            'projects',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', sa.String(255), nullable=True),
            sa.Column('name', sa.String(60), nullable=False),
            sa.Column('description', sa.Text(), nullable=False, server_default=''),
            sa.Column('status', sa.String(30), nullable=False, server_default='empty'),
            sa.Column('analysis_id', sa.String(255), nullable=True),
            sa.Column('mode', sa.String(30), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_projects_user_id', 'projects', ['user_id'])

    # ── session_status_enum (PostgreSQL enum type) ────────────────────────────
    # Must exist before the sessions table is created.
    enum_exists = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'session_status_enum'")
    ).fetchone()
    if not enum_exists:
        sa.Enum(
            'draft', 'processing', 'completed', 'error',
            name='session_status_enum',
        ).create(bind)

    # ── sessions ──────────────────────────────────────────────────────────────
    if 'sessions' not in tables:
        op.create_table(
            'sessions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                'status',
                sa.Enum(
                    'draft', 'processing', 'completed', 'error',
                    name='session_status_enum',
                    create_type=False,   # already created above
                ),
                nullable=False,
                server_default='draft',
            ),
            sa.Column('provider', sa.String(20), nullable=False, server_default='ollama'),
            sa.Column('filename', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_sessions_project_id', 'sessions', ['project_id'])

    # ── signals ───────────────────────────────────────────────────────────────
    if 'signals' not in tables:
        op.create_table(
            'signals',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('signal_name', sa.String(60), nullable=False),
            sa.Column('value', sa.String(60), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('source_text', sa.Text(), nullable=False, server_default=''),
            sa.Column('page_number', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('source_verified', sa.Boolean(), nullable=False,
                      server_default=sa.text('false')),
            sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_signals_session_id', 'signals', ['session_id'])
        op.create_index('ix_signals_session_name', 'signals', ['session_id', 'signal_name'])

    # ── results ───────────────────────────────────────────────────────────────
    if 'results' not in tables:
        op.create_table(
            'results',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('recommended_architecture', sa.String(60), nullable=False),
            sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('ranking',             postgresql.JSONB(), nullable=False, server_default='[]'),
            sa.Column('scores',              postgresql.JSONB(), nullable=False, server_default='{}'),
            sa.Column('decision_breakdown',  postgresql.JSONB(), nullable=False, server_default='{}'),
            sa.Column('why_not',             postgresql.JSONB(), nullable=False, server_default='{}'),
            sa.Column('suitability',         postgresql.JSONB(), nullable=False, server_default='{}'),
            sa.Column('followup_questions',  postgresql.JSONB(), nullable=False, server_default='[]'),
            sa.Column('sensitivity',         postgresql.JSONB(), nullable=False, server_default='{}'),
            sa.Column('decision_trace',      postgresql.JSONB(), nullable=False, server_default='[]'),
            sa.Column('architecture_details',postgresql.JSONB(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('session_id', name='uq_results_session_id'),
        )
        op.create_index('ix_results_session_id', 'results', ['session_id'])


def downgrade() -> None:
    # Intentionally a no-op.
    # This is a baseline "create if missing" migration — dropping tables here
    # would destroy production data on rollback, which is never safe.
    pass
