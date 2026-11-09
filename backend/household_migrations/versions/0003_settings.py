"""Reversible settings retirement and pre-Link import date."""
import sqlalchemy as sa
from alembic import op

revision = "0003_settings"
down_revision = "0002_banks"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("hh_accounts", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("hh_categories", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("hh_bank_links", sa.Column("start_date", sa.Date(), nullable=True))

def downgrade():
    op.drop_column("hh_bank_links", "start_date")
    op.drop_column("hh_categories", "archived")
    op.drop_column("hh_accounts", "archived")
