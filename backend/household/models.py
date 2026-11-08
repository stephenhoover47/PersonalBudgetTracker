from datetime import date

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Household(Base):
    __tablename__ = "hh_households"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(default=0)


class User(Base):
    __tablename__ = "hh_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(256))


class Session(Base):
    __tablename__ = "hh_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("hh_users.id"))
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[int] = mapped_column(Integer)


class LoginAttempt(Base):
    __tablename__ = "hh_login_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    window: Mapped[int] = mapped_column(Integer)


class Account(Base):
    archived: Mapped[bool] = mapped_column(default=False)
    __tablename__ = "hh_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    __table_args__ = (
        UniqueConstraint("household_id", "name"),
        CheckConstraint("kind IN ('checking','credit','savings')"),
    )


class Category(Base):
    archived: Mapped[bool] = mapped_column(default=False)
    __tablename__ = "hh_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    mode: Mapped[str] = mapped_column(String(20))
    __table_args__ = (
        UniqueConstraint("household_id", "name"),
        CheckConstraint("mode IN ('fixed','flexible')"),
    )


class Transaction(Base):
    __tablename__ = "hh_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("hh_accounts.id"))
    date: Mapped[date]
    merchant: Mapped[str] = mapped_column(String(200))
    cents: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30), default="review")
    fingerprint: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(30), default="csv")
    external_id: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (
        UniqueConstraint("account_id", "fingerprint"),
        CheckConstraint("cents != 0"),
        CheckConstraint(
            "kind IN ('review','expense','refund','reimbursement','income','contribution','transfer','card_payment','savings','loan_payment')"
        ),
        Index("hh_tx_month", "household_id", "date"),
    )


class Split(Base):
    __tablename__ = "hh_splits"
    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("hh_transactions.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int] = mapped_column(ForeignKey("hh_categories.id"))
    cents: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("transaction_id", "category_id"),)


class Budget(Base):
    __tablename__ = "hh_budgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("hh_categories.id"))
    month: Mapped[str] = mapped_column(String(7))
    cents: Mapped[int] = mapped_column(Integer)
    rollover: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (
        UniqueConstraint("household_id", "category_id", "month"),
        CheckConstraint("cents >= 0"),
    )


class Savings(Base):
    __tablename__ = "hh_savings"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    month: Mapped[str] = mapped_column(String(7))
    cents: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint("household_id", "name", "month"),
        CheckConstraint("cents >= 0"),
    )


class ImportBatch(Base):
    __tablename__ = "hh_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("hh_accounts.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("hh_users.id"))
    rows: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="preview")
    created: Mapped[int] = mapped_column(Integer)
    imported: Mapped[int] = mapped_column(default=0)
    duplicates: Mapped[int] = mapped_column(default=0)


class Audit(Base):
    __tablename__ = "hh_audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("hh_users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource: Mapped[str] = mapped_column(String(100))
    created: Mapped[int] = mapped_column(Integer)


class BankLink(Base):
    start_date: Mapped[date | None]
    __tablename__ = "hh_bank_links"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("hh_users.id"))
    token: Mapped[str] = mapped_column(String(2000))
    created: Mapped[int] = mapped_column(Integer)
    completed: Mapped[bool] = mapped_column(default=False)


class BankItem(Base):
    __tablename__ = "hh_bank_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("hh_households.id"), index=True)
    provider_id: Mapped[str] = mapped_column(String(200), unique=True)
    token: Mapped[str] = mapped_column(String(2000))
    accounts: Mapped[list] = mapped_column(JSON)
    account_map: Mapped[dict] = mapped_column(JSON, default=dict)
    start_date: Mapped[date | None]
    cursor: Mapped[str | None] = mapped_column(String(2000))
    last_sync: Mapped[int | None] = mapped_column(Integer)
