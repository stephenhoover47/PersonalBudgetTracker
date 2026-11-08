"""Encrypted, household-scoped bank connections."""
from alembic import op

from household.models import BankItem, BankLink

revision = "0002_banks"
down_revision = "0001_household"
branch_labels = None
depends_on = None

def upgrade():
    BankLink.__table__.create(op.get_bind())
    BankItem.__table__.create(op.get_bind())

def downgrade():
    BankItem.__table__.drop(op.get_bind())
    BankLink.__table__.drop(op.get_bind())
