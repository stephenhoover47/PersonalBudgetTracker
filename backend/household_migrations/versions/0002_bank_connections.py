"""Encrypted, household-scoped bank connections. Frozen original schema."""
import sqlalchemy as sa
from alembic import op

revision = "0002_banks"
down_revision = "0001_household"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("hh_bank_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("hh_households.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("hh_users.id"), nullable=False),
        sa.Column("token", sa.String(2000), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False))
    op.create_index("ix_hh_bank_links_household_id", "hh_bank_links", ["household_id"])
    op.create_table("hh_bank_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("hh_households.id"), nullable=False),
        sa.Column("provider_id", sa.String(200), nullable=False, unique=True),
        sa.Column("token", sa.String(2000), nullable=False),
        sa.Column("accounts", sa.JSON(), nullable=False),
        sa.Column("account_map", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("cursor", sa.String(2000), nullable=True),
        sa.Column("last_sync", sa.Integer(), nullable=True))
    op.create_index("ix_hh_bank_items_household_id", "hh_bank_items", ["household_id"])


def downgrade():
    op.drop_table("hh_bank_items")
    op.drop_table("hh_bank_links")
