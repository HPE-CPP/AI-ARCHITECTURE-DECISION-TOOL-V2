"""add error_message to sessions

Revision ID: 3ff76c9d74bf
Revises: c1d2e3f4a5b6
Create Date: 2026-06-19 13:00:50.507246

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ff76c9d74bf'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'sessions' in tables:
        op.add_column('sessions', sa.Column('error_message', sa.Text(), nullable=True))
    if 'signals' in tables:
        op.create_index('ix_signals_session_name', 'signals', ['session_id', 'signal_name'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'signals' in tables:
        op.drop_index('ix_signals_session_name', table_name='signals')
    if 'sessions' in tables:
        op.drop_column('sessions', 'error_message')
