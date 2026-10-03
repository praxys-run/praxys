"""Metadata-inferred proof, sync receipts and durable activity rights fences."""
from alembic import op
import sqlalchemy as sa

revision = 'c5e6f7a81920'
down_revision = 'b4d5f6a70819'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('activity_dfa_metadata_proofs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('activity_id',sa.String(100),nullable=False),
        sa.Column('snapshot_id',sa.String(36),sa.ForeignKey('garmin_fit_snapshots.id',ondelete='CASCADE'),nullable=False),
        sa.Column('parse_id',sa.String(36),sa.ForeignKey('garmin_fit_parses.id',ondelete='CASCADE'),nullable=False),
        sa.Column('recording_ref',sa.JSON(),nullable=False),
        sa.Column('source_evidence_digest',sa.String(64),nullable=False),
        sa.Column('source_contract_digest',sa.String(71),nullable=False),
        sa.Column('source_rule_version',sa.String(80),nullable=False),
        sa.Column('metadata_projection_version',sa.String(80),nullable=False),
        sa.Column('candidates',sa.JSON(),nullable=False),
        sa.Column('identity_digest',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('user_id','identity_digest',name='uq_dfa_metadata_proof_identity'))
    op.create_index('ix_activity_dfa_metadata_proofs_user_id','activity_dfa_metadata_proofs',['user_id'])
    op.create_table('activity_dfa_rights_state',
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('activity_id',sa.String(100),primary_key=True),
        sa.Column('suppressed',sa.Boolean(),nullable=False),
        sa.Column('generation',sa.Integer(),nullable=False),
        sa.Column('reason',sa.String(40),nullable=False),
        sa.Column('changed_at',sa.DateTime(),nullable=False),
        sa.CheckConstraint('generation >= 0',name='ck_dfa_rights_generation'))
    op.create_index('ix_dfa_rights_pending','activity_dfa_rights_state',['reason','changed_at'])
    with op.batch_alter_table('activity_dfa_runs') as batch:
        batch.add_column(sa.Column('origin',sa.String(16),nullable=False,server_default='manual'))
        batch.add_column(sa.Column('source_assurance',sa.String(24),nullable=False,server_default='user_confirmed'))
        batch.add_column(sa.Column('metadata_proof_id',sa.String(36),nullable=True))
        batch.create_foreign_key('fk_dfa_metadata_proof','activity_dfa_metadata_proofs',['metadata_proof_id'],['id'],ondelete='CASCADE')
        batch.add_column(sa.Column('rights_generation',sa.Integer(),nullable=False,server_default='0'))
        batch.create_check_constraint('ck_dfa_source_branch',"(origin = 'manual' AND source_assurance = 'user_confirmed' AND metadata_proof_id IS NULL) OR (origin = 'automatic' AND source_assurance = 'metadata_inferred' AND confirmation_id IS NULL)")
        batch.create_check_constraint('ck_dfa_run_rights','rights_generation >= 0')
        batch.drop_constraint('ck_dfa_state',type_='check')
        batch.create_check_constraint('ck_dfa_state',"status IN ('queued','running','awaiting_source_confirmation','complete','unavailable','failed','cancelled','gate_paused')")
    op.create_table('activity_dfa_receipts',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('activity_id',sa.String(100),nullable=False),
        sa.Column('provider',sa.String(40),nullable=False),
        sa.Column('account_id',sa.String(100),nullable=True),
        sa.Column('recording_ref',sa.JSON(),nullable=True),
        sa.Column('event_digest',sa.String(64),nullable=False),
        sa.Column('generation',sa.Integer(),nullable=False),
        sa.Column('rights_generation',sa.Integer(),nullable=False),
        sa.Column('status',sa.String(40),nullable=False),
        sa.Column('reason',sa.String(80),nullable=True),
        sa.Column('run_id',sa.String(36),sa.ForeignKey('activity_dfa_runs.id',ondelete='SET NULL'),nullable=True),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.Column('checked_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('user_id','event_digest',name='uq_dfa_receipt_event'))
    if op.get_bind().dialect.name == 'sqlite':
        op.execute("CREATE TRIGGER dfa_metadata_proofs_immutable BEFORE UPDATE ON activity_dfa_metadata_proofs BEGIN SELECT RAISE(ABORT,'DFA metadata proofs are immutable'); END")
    else:
        op.execute("CREATE FUNCTION dfa_metadata_proofs_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'DFA metadata proofs are immutable'; END $$")
        op.execute("CREATE TRIGGER dfa_metadata_proofs_immutable BEFORE UPDATE ON activity_dfa_metadata_proofs FOR EACH ROW EXECUTE FUNCTION dfa_metadata_proofs_immutable()")
    op.create_index('ix_activity_dfa_receipts_user_id','activity_dfa_receipts',['user_id'])
    op.create_index('ix_dfa_receipt_scan','activity_dfa_receipts',['status','checked_at','user_id','id'])


def downgrade():
    # Do not discard durable suppression automatically; an older binary cannot
    # safely honor the approved rights contract. Use a compatible rollback build.
    raise RuntimeError('DFA automatic rights data requires a compatible rollback artifact')
