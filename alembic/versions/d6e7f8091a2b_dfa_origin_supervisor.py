"""Separate DFA origin authority and pinned physical control, initially disabled."""
from alembic import op
import sqlalchemy as sa
revision = 'd6e7f8091a2b'
down_revision = 'b4d5f6a70819'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user_connections', sa.Column('dfa_account_generation', sa.String(36)))
    for column in [sa.Column('origin', sa.String(12), nullable=False, server_default='manual'),
                   sa.Column('grant_id', sa.String(36)), sa.Column('admission_id', sa.String(36)),
                   sa.Column('accepted_at', sa.DateTime()), sa.Column('execution_epoch', sa.String(64))]:
        op.add_column('activity_dfa_runs', column)
    op.drop_index('uq_dfa_active_owner', table_name='activity_dfa_runs')
    op.create_index('uq_dfa_active_owner', 'activity_dfa_runs', ['user_id','origin'], unique=True,
                    sqlite_where=sa.text("status IN ('queued','running')"),
                    postgresql_where=sa.text("status IN ('queued','running')"))
    op.create_table('activity_dfa_origin_grants',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('origin',sa.String(12),nullable=False),sa.Column('binding_digest',sa.String(64),nullable=False),
        sa.Column('binding',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('user_id','origin','binding_digest',name='uq_dfa_origin_grant'),
        sa.CheckConstraint("origin IN ('manual','automatic')",name='ck_dfa_grant_origin'))
    op.create_table('activity_dfa_sync_grants',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('account_id',sa.String(128),nullable=False),sa.Column('account_generation',sa.String(36),nullable=False),
        sa.Column('connection_id',sa.Integer(),nullable=False),sa.Column('action',sa.String(40),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('user_id','account_id','account_generation',name='uq_dfa_sync_grant'))
    op.create_table('activity_dfa_sync_receipts',
        sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('recording_ref',sa.JSON(),nullable=False),sa.Column('completion_revision',sa.String(64),nullable=False),
        sa.Column('account_generation',sa.String(36),nullable=False),sa.Column('sync_grant_id',sa.String(36),nullable=False),
        sa.Column('disposition',sa.String(32),nullable=False),sa.Column('run_id',sa.String(36)),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    for table in ['activity_dfa_origin_grants','activity_dfa_sync_grants','activity_dfa_sync_receipts']:
        op.create_index('ix_'+table+'_user_id',table,['user_id'])
    op.create_table('activity_dfa_control',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('incarnation',sa.JSON()),sa.Column('enabled',sa.Boolean(),nullable=False),
        sa.Column('drained',sa.Boolean(),nullable=False),sa.Column('epoch',sa.Integer(),nullable=False),
        sa.Column('manual_sequence',sa.Integer(),nullable=False),sa.Column('readiness_sequence',sa.Integer(),nullable=False),
        sa.Column('ready_until',sa.DateTime()),sa.Column('actor',sa.JSON()),
        sa.CheckConstraint('id = 1',name='ck_dfa_control_singleton'))
    op.execute(sa.text('INSERT INTO activity_dfa_control(id,enabled,drained,epoch,manual_sequence,readiness_sequence) VALUES(1,false,true,1,0,0)'))


def downgrade():
    # Emergency recovery retains grants, actor and journal references. A reviewed
    # drained destructive schema reversal is deliberately not an implicit action.
    raise RuntimeError('DFA downgrade requires independently verified physical drain')
