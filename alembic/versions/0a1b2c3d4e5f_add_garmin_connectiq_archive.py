"""Private original FIT snapshots, projections and durable Connect IQ jobs."""
from alembic import op
import sqlalchemy as sa

revision = "0a1b2c3d4e5f"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('garmin_fit_snapshots',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=False, nullable=False),
        sa.Column('account_id', sa.String(length=100), primary_key=False, nullable=False),
        sa.Column('activity_id', sa.String(length=100), primary_key=False, nullable=False),
        sa.Column('sha256', sa.String(length=64), primary_key=False, nullable=False),
        sa.Column('raw_fit', sa.LargeBinary(), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), primary_key=False, nullable=False),
        sa.Column('active_parse_id', sa.String(length=36), primary_key=False, nullable=True),
        sa.UniqueConstraint('user_id', 'account_id', 'activity_id', 'sha256', name='uq_garmin_fit_snapshot'),
    )
    op.create_index('ix_garmin_fit_snapshots_user_id', 'garmin_fit_snapshots', ['user_id'])
    op.create_table('garmin_fit_parses',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=False, nullable=False),
        sa.Column('snapshot_id', sa.String(length=36), sa.ForeignKey('garmin_fit_snapshots.id', ondelete='CASCADE'), primary_key=False, nullable=False),
        sa.Column('parser_version', sa.String(length=80), primary_key=False, nullable=False),
        sa.Column('status', sa.String(length=30), primary_key=False, nullable=False),
        sa.Column('error_code', sa.String(length=80), primary_key=False, nullable=True),
        sa.Column('catalog', sa.JSON(), primary_key=False, nullable=False),
        sa.Column('frame_count', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('developer_field_count', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), primary_key=False, nullable=False),
    )
    op.create_index('ix_garmin_fit_parses_snapshot_id', 'garmin_fit_parses', ['snapshot_id'])
    op.create_index('ix_garmin_fit_parses_user_id', 'garmin_fit_parses', ['user_id'])
    op.create_table('garmin_fit_chunks',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=False, nullable=False),
        sa.Column('parse_id', sa.String(length=36), sa.ForeignKey('garmin_fit_parses.id', ondelete='CASCADE'), primary_key=False, nullable=False),
        sa.Column('chunk_index', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('frames', sa.JSON(), primary_key=False, nullable=False),
        sa.UniqueConstraint('parse_id', 'chunk_index', name='uq_garmin_fit_chunk'),
    )
    op.create_index('ix_garmin_fit_chunks_user_id', 'garmin_fit_chunks', ['user_id'])
    op.create_table('garmin_connectiq_jobs',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=False, nullable=False),
        sa.Column('account_id', sa.String(length=100), primary_key=False, nullable=True),
        sa.Column('credential_generation', sa.String(length=160), primary_key=False, nullable=False),
        sa.Column('region', sa.String(length=20), primary_key=False, nullable=False),
        sa.Column('kind', sa.String(length=20), primary_key=False, nullable=False),
        sa.Column('from_date', sa.Date(), primary_key=False, nullable=True),
        sa.Column('to_date', sa.Date(), primary_key=False, nullable=True),
        sa.Column('discovery_date', sa.Date(), primary_key=False, nullable=True),
        sa.Column('discovery_offset', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('discovery_complete', sa.Boolean(), primary_key=False, nullable=False),
        sa.Column('status', sa.String(length=30), primary_key=False, nullable=False),
        sa.Column('lease_token', sa.String(length=36), primary_key=False, nullable=True),
        sa.Column('lease_until', sa.DateTime(), primary_key=False, nullable=True),
        sa.Column('next_retry_at', sa.DateTime(), primary_key=False, nullable=True),
        sa.Column('attempts', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('error_code', sa.String(length=80), primary_key=False, nullable=True),
        sa.Column('created_at', sa.DateTime(), primary_key=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(), primary_key=False, nullable=False),
    )
    op.create_index("uq_garmin_connectiq_running_owner", "garmin_connectiq_jobs", ["user_id"],
                    unique=True, sqlite_where=sa.text("status = 'running'"),
                    postgresql_where=sa.text("status = 'running'"))
    op.create_index('ix_garmin_connectiq_jobs_status', 'garmin_connectiq_jobs', ['status'])
    op.create_index('ix_garmin_connectiq_jobs_user_id', 'garmin_connectiq_jobs', ['user_id'])
    op.create_table('garmin_connectiq_items',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=False, nullable=False),
        sa.Column('job_id', sa.String(length=36), sa.ForeignKey('garmin_connectiq_jobs.id', ondelete='CASCADE'), primary_key=False, nullable=False),
        sa.Column('activity_id', sa.String(length=100), primary_key=False, nullable=False),
        sa.Column('status', sa.String(length=30), primary_key=False, nullable=False),
        sa.Column('snapshot_id', sa.String(length=36), sa.ForeignKey('garmin_fit_snapshots.id', ondelete='SET NULL'), primary_key=False, nullable=True),
        sa.Column('error_code', sa.String(length=80), primary_key=False, nullable=True),
        sa.Column('attempts', sa.Integer(), primary_key=False, nullable=False),
        sa.UniqueConstraint('job_id', 'activity_id', name='uq_garmin_connectiq_item'),
    )
    op.create_index('ix_garmin_connectiq_items_user_id', 'garmin_connectiq_items', ['user_id'])


def downgrade():
    op.drop_table('garmin_connectiq_items')
    op.drop_table('garmin_connectiq_jobs')
    op.drop_table('garmin_fit_chunks')
    op.drop_table('garmin_fit_parses')
    op.drop_table('garmin_fit_snapshots')
