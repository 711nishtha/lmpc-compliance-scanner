"""add rule_verifications audit table

Records human sign-off on a NEEDS_VERIFICATION rule result (see app/models/orm.py's
RuleVerification and api/scans.py::verify_rule_result). The upgraded status is also materialised
into scans.rule_results_json, but that column can be recomputed or overwritten by a rescan --
this table is the durable record of who signed off on what, and when.

Revision ID: a3f81c7d9e42
Revises: 11b647e2d849
Create Date: 2026-09-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f81c7d9e42'
down_revision: Union[str, Sequence[str], None] = '11b647e2d849'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'rule_verifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.String(length=32), nullable=False),
        sa.Column('original_status', sa.String(length=32), nullable=False),
        sa.Column('new_status', sa.String(length=32), nullable=False),
        sa.Column('verified_by', sa.String(length=255), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_rule_verifications_scan_id'), 'rule_verifications', ['scan_id'])
    op.create_index(op.f('ix_rule_verifications_rule_id'), 'rule_verifications', ['rule_id'])
    op.create_index(op.f('ix_rule_verifications_verified_by'), 'rule_verifications', ['verified_by'])
    op.create_index(op.f('ix_rule_verifications_created_at'), 'rule_verifications', ['created_at'])


def downgrade() -> None:
    """Downgrade schema.

    Drops the audit trail. Deliberately called out rather than left as boilerplate: downgrading
    past this revision destroys the record of who signed off on which findings, which is not
    recoverable from scans.rule_results_json alone (that column keeps the resulting status but
    not the history). Export the table before running this against anything real.
    """
    op.drop_index(op.f('ix_rule_verifications_created_at'), table_name='rule_verifications')
    op.drop_index(op.f('ix_rule_verifications_verified_by'), table_name='rule_verifications')
    op.drop_index(op.f('ix_rule_verifications_rule_id'), table_name='rule_verifications')
    op.drop_index(op.f('ix_rule_verifications_scan_id'), table_name='rule_verifications')
    op.drop_table('rule_verifications')
