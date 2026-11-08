import csv
import hashlib
import logging
import os
import secrets
import time
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import String, case, delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from .db import database_url, make_engine
from .ingestion import parse_csv
from .models import (
    Account,
    Audit,
    Budget,
    Category,
    Household,
    ImportBatch,
    LoginAttempt,
    Savings,
    Session,
    Split,
    Transaction,
    User,
)
from .schemas import (
    AccountIn,
    BudgetIn,
    Bulk,
    CategoryIn,
    CommitImport,
    CopyMonth,
    Edit,
    ImportIn,
    Login,
    PlanIn,
    SavingsIn,
)

logger = logging.getLogger("household")
passwords = PasswordHasher()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
SPENDING = {"expense", "refund", "reimbursement", "loan_payment"}
MAX_SESSION = 60 * 60 * 24 * 7


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def month_value(value):
    try:
        if (
            len(value) != 7
            or datetime.strptime(value, "%Y-%m").strftime("%Y-%m") != value
            or not "2000-01" <= value <= "2100-12"
        ):
            raise ValueError()
        return value
    except ValueError:
        raise HTTPException(422, "Month must be YYYY-MM, 2000–2100")


def previous(month):
    y, m = map(int, month.split("-"))
    return f"{y if m > 1 else y - 1:04d}-{m - 1 if m > 1 else 12:02d}"


def create_app(url=None, *, testing=False):
    production = os.getenv("APP_ENV") == "production" and not testing
    origin = os.getenv("APP_ORIGIN", "http://localhost:5173").rstrip("/")
    if production and not origin.startswith("https://"):
        raise RuntimeError("Production requires HTTPS APP_ORIGIN")
    if production and url is None:
        configured = os.getenv("DATABASE_URL", "")
        if not configured.startswith(("postgresql://", "postgres://")):
            raise RuntimeError("Production requires an explicit PostgreSQL DATABASE_URL")
    engine = make_engine(url or database_url())
    factory = sessionmaker(engine, expire_on_commit=False)
    app = FastAPI(
        title="Household Budget", docs_url=None if production else "/docs", redoc_url=None
    )
    app.state.engine = engine
    app.state.factory = factory

    @app.middleware("http")
    async def security(request, call_next):
        request_id = uuid4().hex
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            # Browser form attacks cannot set this header; session token is also checked below.
            if (
                request.headers.get("origin") not in {None, origin}
                or request.headers.get("x-requested-with") != "household"
            ):
                return JSONResponse({"detail": "Request origin/header rejected"}, status_code=403)
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Invalid content length"}, status_code=400)
            if length > 2500000:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
            # Bound chunked requests as well as Content-Length requests.
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 2500000:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        start = time.monotonic()
        response = await call_next(request)
        response.headers.update(
            {
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "same-origin",
                "X-Frame-Options": "DENY",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            }
        )
        if production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        logger.info(
            "request id=%s method=%s status=%s duration_ms=%d",
            request_id,
            request.method,
            response.status_code,
            int((time.monotonic() - start) * 1000),
        )
        return response

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return JSONResponse({"detail": "Conflicting record. Refresh and retry."}, status_code=409)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        # Do not log DB exception strings: they can contain financial values and credentials.
        logger.error("request failed type=%s", type(exc).__name__)
        return JSONResponse({"detail": "Unexpected server error"}, status_code=500)

    def db():
        with factory() as session:
            try:
                yield session
            finally:
                session.rollback()

    def current(request: Request, session=Depends(db)):
        token = request.cookies.get("hh_session", "")
        auth = session.get(Session, digest(token)) if token else None
        if not auth or auth.expires <= int(time.time()):
            raise HTTPException(401, "Sign in required")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not secrets.compare_digest(
            request.headers.get("x-csrf-token", ""), auth.csrf
        ):
            raise HTTPException(403, "Invalid CSRF token")
        user = session.get(User, auth.user_id)
        request.state.auth = auth
        return user

    def owned(session, model, ident, user):
        value = session.get(model, ident)
        if not value or value.household_id != user.household_id:
            raise HTTPException(404, "Record not found")
        return value

    def lock(session, user):
        # Serializes household mutations across workers (also takes SQLite's write lock).
        session.execute(
            update(Household)
            .where(Household.id == user.household_id)
            .values(revision=Household.revision + 1)
        )

    def audit(session, user, action, resource):
        session.add(
            Audit(
                household_id=user.household_id,
                user_id=user.id,
                action=action,
                resource=str(resource),
                created=int(time.time()),
            )
        )

    def scoped(session, model, user):
        return session.scalars(
            select(model).where(model.household_id == user.household_id).order_by(model.id)
        ).all()

    def tx_dict(session, tx):
        return dict(
            id=tx.id,
            account_id=tx.account_id,
            date=tx.date.isoformat(),
            merchant=tx.merchant,
            cents=tx.cents,
            kind=tx.kind,
            version=tx.version,
            splits=[
                dict(category_id=s.category_id, cents=s.cents)
                for s in session.scalars(select(Split).where(Split.transaction_id == tx.id))
            ],
        )

    def apply_edit(session, tx, kind, allocations, user):
        if kind in {"expense", "loan_payment"} and tx.cents < 0:
            raise HTTPException(422, "Expenses/loan payments must be outflows")
        if kind in {"refund", "reimbursement", "income", "contribution"} and tx.cents > 0:
            raise HTTPException(422, "Refunds/reimbursements/income/contributions must be inflows")
        if kind in SPENDING:
            if not allocations or sum(s.cents for s in allocations) != tx.cents:
                raise HTTPException(
                    422, "Spending allocations must equal transaction cents exactly"
                )
            if len({s.category_id for s in allocations}) != len(allocations):
                raise HTTPException(422, "Combine allocations for the same category")
            for s in allocations:
                owned(session, Category, s.category_id, user)
                if not s.cents or (s.cents > 0) != (tx.cents > 0):
                    raise HTTPException(422, "Splits must have the same sign as the transaction")
        elif allocations:
            raise HTTPException(422, "Only spending/refunds have category allocations")
        session.execute(delete(Split).where(Split.transaction_id == tx.id))
        session.add_all(
            [
                Split(transaction_id=tx.id, category_id=s.category_id, cents=s.cents)
                for s in allocations
            ]
        )
        tx.kind, tx.version = kind, tx.version + 1

    @app.get("/health")
    def health(session=Depends(db)):
        session.execute(text("SELECT 1"))
        session.execute(select(Household.id).limit(1))
        return {"status": "ok"}

    @app.post("/api/auth/login")
    def login(payload: Login, request: Request, response: Response, session=Depends(db)):
        now = int(time.time())
        email = payload.email.strip().casefold()
        # Per account AND per direct peer limits; do not trust forwarded IP headers.
        keys = [
            digest("email:" + email),
            digest("ip:" + (request.client.host if request.client else "unknown")),
        ]
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
        session.execute(delete(LoginAttempt).where(LoginAttempt.window < now - 900))
        counts = []
        for key in keys:
            statement = insert(LoginAttempt).values(key=key, count=1, window=now)
            statement = statement.on_conflict_do_update(
                index_elements=[LoginAttempt.key],
                set_={"count": LoginAttempt.count + 1},
            ).returning(LoginAttempt.count)
            counts.append(session.scalar(statement))
        session.commit()
        if max(counts) > 20:
            raise HTTPException(429, "Too many sign-in attempts. Retry in 15 minutes.")
        user = session.scalar(select(User).where(User.email == email))
        try:
            valid = passwords.verify(user.password_hash if user else DUMMY_HASH, payload.password)
        except (VerificationError, InvalidHashError):
            valid = False
        if not user or not valid:
            raise HTTPException(401, "Invalid email or password")
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        old = request.cookies.get("hh_session")
        if old:
            session.execute(delete(Session).where(Session.token_hash == digest(old)))
        session.execute(delete(Session).where(Session.expires <= now))
        session.add(
            Session(token_hash=digest(token), csrf=csrf, user_id=user.id, expires=now + MAX_SESSION)
        )
        session.commit()
        response.set_cookie(
            "hh_session",
            token,
            httponly=True,
            secure=production,
            samesite="strict",
            max_age=MAX_SESSION,
            path="/",
        )
        return {"csrf": csrf}

    @app.get("/api/me")
    def me(request: Request, user=Depends(current), session=Depends(db)):
        household = session.get(Household, user.household_id)
        return {
            "name": user.name,
            "household": household.name,
            "csrf": request.state.auth.csrf,
            "members": [u.name for u in scoped(session, User, user)],
        }

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, user=Depends(current), session=Depends(db)):
        session.delete(request.state.auth)
        session.commit()
        response.delete_cookie("hh_session", path="/")
        return {"ok": True}

    @app.get("/api/accounts")
    def accounts(user=Depends(current), session=Depends(db)):
        return [dict(id=a.id, name=a.name, kind=a.kind, archived=a.archived) for a in scoped(session, Account, user)]

    @app.post("/api/accounts", status_code=201)
    def add_account(payload: AccountIn, user=Depends(current), session=Depends(db)):
        lock(session, user)
        item = Account(household_id=user.household_id, **payload.model_dump())
        session.add(item)
        audit(session, user, "account.create", "account")
        session.commit()
        return {"id": item.id}

    @app.put("/api/accounts/{ident}")
    def edit_account(ident: int, payload: AccountIn, user=Depends(current), session=Depends(db)):
        lock(session, user)
        item = owned(session, Account, ident, user)
        item.name, item.kind = payload.name, payload.kind
        audit(session, user, "account.update", ident)
        session.commit()
        return {"ok": True}

    @app.post("/api/settings/{kind}/{ident}/{action}")
    def retire(kind: Literal["accounts", "categories"], ident: int,
               action: Literal["archive", "restore"], user=Depends(current), session=Depends(db)):
        lock(session, user)
        model = Account if kind == "accounts" else Category
        item = owned(session, model, ident, user)
        if kind == "accounts" and action == "archive":
            from .models import BankItem
            for bank in scoped(session, BankItem, user):
                if bank.token and ident in bank.account_map.values():
                    raise HTTPException(409, "Disconnect this account's bank connection before archiving it.")
        if kind == "categories" and action == "archive" and not item.archived:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            month = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m")
            budget = session.scalar(select(Budget).where(Budget.household_id == user.household_id, Budget.category_id == ident, Budget.month == month))
            if budget is None:
                budget = Budget(household_id=user.household_id, category_id=ident, month=month)
                session.add(budget)
            budget.cents, budget.rollover = 0, False
        item.archived = action == "archive"
        audit(session, user, kind + "." + action, ident)
        session.commit()
        return {"ok": True}

    @app.get("/api/categories")
    def categories(user=Depends(current), session=Depends(db)):
        return [dict(id=c.id, name=c.name, mode=c.mode, archived=c.archived) for c in scoped(session, Category, user)]

    @app.post("/api/categories", status_code=201)
    def add_category(payload: CategoryIn, user=Depends(current), session=Depends(db)):
        lock(session, user)
        item = Category(household_id=user.household_id, **payload.model_dump())
        session.add(item)
        audit(session, user, "category.create", "category")
        session.commit()
        return {"id": item.id}

    @app.put("/api/categories/{ident}")
    def edit_category(ident: int, payload: CategoryIn, user=Depends(current), session=Depends(db)):
        lock(session, user)
        item = owned(session, Category, ident, user)
        item.name, item.mode = payload.name, payload.mode
        audit(session, user, "category.update", ident)
        session.commit()
        return {"ok": True}

    @app.get("/api/transactions")
    def transactions(
        month: str,
        search: str = Query("", max_length=200),
        kind: str | None = None,
        account_id: int | None = None,
        category_id: int | None = None,
        sort: Literal["newest", "oldest", "largest", "smallest"] = "newest",
        credits_first: bool = False,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=200),
        user=Depends(current),
        session=Depends(db),
    ):
        month_value(month)
        query = select(Transaction).where(
            Transaction.household_id == user.household_id,
            Transaction.date >= date.fromisoformat(month + "-01"),
            Transaction.date < next_month(month),
        )
        if search:
            query = query.where(Transaction.merchant.icontains(search, autoescape=True))
        if kind:
            query = query.where(Transaction.kind == kind)
        if account_id:
            query = query.where(Transaction.account_id == account_id)
        if category_id:
            query = query.where(
                Transaction.id.in_(
                    select(Split.transaction_id).where(Split.category_id == category_id)
                )
            )
        total = session.scalar(select(func.count()).select_from(query.subquery()))
        # Sort in SQL before pagination. Only spending credits belong in refunds-first.
        ordering = {
            "newest": Transaction.date.desc(), "oldest": Transaction.date.asc(),
            "largest": Transaction.cents.desc(), "smallest": Transaction.cents.asc(),
        }
        priority = [case((Transaction.kind.in_(["refund", "reimbursement"]), 0), else_=1)] if credits_first else []
        items = session.scalars(
            query.order_by(*priority, ordering[sort], Transaction.date.desc(), Transaction.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return {"total": total, "items": [tx_dict(session, t) for t in items]}

    @app.put("/api/transactions/{ident}")
    def edit_transaction(ident: int, payload: Edit, user=Depends(current), session=Depends(db)):
        lock(session, user)
        tx = owned(session, Transaction, ident, user)
        if tx.version != payload.version:
            raise HTTPException(409, "Transaction changed. Refresh before editing.")
        apply_edit(session, tx, payload.kind, payload.splits, user)
        audit(session, user, "transaction.edit", ident)
        session.commit()
        return tx_dict(session, tx)

    @app.post("/api/transactions/bulk")
    def bulk(payload: Bulk, user=Depends(current), session=Depends(db)):
        from .schemas import Allocation

        lock(session, user)
        for ident, version in payload.transactions.items():
            tx = owned(session, Transaction, ident, user)
            if tx.version != version:
                raise HTTPException(409, "A transaction changed. Refresh before editing.")
            splits = (
                [Allocation(category_id=payload.category_id, cents=tx.cents)]
                if payload.category_id
                else []
            )
            apply_edit(session, tx, payload.kind, splits, user)
            audit(session, user, "transaction.bulk", ident)
        session.commit()
        return {"updated": len(payload.transactions)}

    @app.post("/api/imports/preview")
    def preview(payload: ImportIn, user=Depends(current), session=Depends(db)):
        if owned(session, Account, payload.account_id, user).archived:
            raise HTTPException(409, "Restore this account before importing transactions")
        try:
            rows = parse_csv(payload.csv, payload.format, payload.outflows_positive)
        except (ValueError, csv.Error) as exc:
            raise HTTPException(422, str(exc))
        existing = {
            t.fingerprint: t
            for t in session.scalars(
                select(Transaction).where(Transaction.account_id == payload.account_id)
            )
        }
        duplicates = 0
        for row in rows:
            old = existing.get(row["fingerprint"])
            row["duplicate"] = bool(old)
            if old:
                if old.cents != row["cents"] or old.date.isoformat() != row["date"]:
                    raise HTTPException(
                        409,
                        "An existing external ID has changed amount/date. Reconcile the source export before importing.",
                    )
                duplicates += 1
        batch = ImportBatch(
            household_id=user.household_id,
            account_id=payload.account_id,
            created_by=user.id,
            rows=rows,
            created=int(time.time()),
        )
        session.add(batch)
        session.commit()
        return {
            "id": batch.id,
            "rows": rows,
            "duplicates": duplicates,
            "net_cents": sum(r["cents"] for r in rows),
            "new_net_cents": sum(r["cents"] for r in rows if not r["duplicate"]),
        }

    @app.post("/api/imports/{ident}/commit")
    def commit_import(
        ident: int, payload: CommitImport, user=Depends(current), session=Depends(db)
    ):
        lock(session, user)
        batch = owned(session, ImportBatch, ident, user)
        if owned(session, Account, batch.account_id, user).archived:
            raise HTTPException(409, "Restore this account before importing transactions")
        if batch.status != "preview":
            raise HTTPException(409, "Import already committed")
        if batch.created < int(time.time()) - 86400:
            raise HTTPException(409, "Preview expired. Upload again.")
        if payload.expected_net_cents != sum(r["cents"] for r in batch.rows):
            raise HTTPException(422, "Reconciliation total does not match CSV net")
        existing = {
            t.fingerprint: t
            for t in session.scalars(
                select(Transaction).where(Transaction.account_id == batch.account_id)
            )
        }
        for row in batch.rows:
            old = existing.get(row["fingerprint"])
            if old:
                if old.cents != row["cents"] or old.date.isoformat() != row["date"]:
                    raise HTTPException(409, "Existing external ID conflicts with import")
                batch.duplicates += 1
                continue
            session.add(
                Transaction(
                    household_id=user.household_id,
                    account_id=batch.account_id,
                    date=date.fromisoformat(row["date"]),
                    merchant=row["merchant"],
                    cents=row["cents"],
                    fingerprint=row["fingerprint"],
                    external_id=row["external_id"],
                    kind="review",
                )
            )
            batch.imported += 1
        batch.status = "committed"
        audit(session, user, "import.commit", ident)
        session.commit()
        return {"imported": batch.imported, "duplicates": batch.duplicates}

    @app.get("/api/imports")
    def imports(user=Depends(current), session=Depends(db)):
        items = session.scalars(
            select(ImportBatch)
            .where(ImportBatch.household_id == user.household_id)
            .order_by(ImportBatch.id.desc())
            .limit(50)
        )
        return [
            dict(
                id=b.id,
                account_id=b.account_id,
                status=b.status,
                created=b.created,
                imported=b.imported,
                duplicates=b.duplicates,
            )
            for b in items
        ]

    @app.put("/api/budgets/{month}/{category_id}")
    def budget(
        month: str, category_id: int, payload: BudgetIn, user=Depends(current), session=Depends(db)
    ):
        month_value(month)
        lock(session, user)
        owned(session, Category, category_id, user)
        item = session.scalar(
            select(Budget).where(
                Budget.household_id == user.household_id,
                Budget.category_id == category_id,
                Budget.month == month,
            )
        )
        if item is None:
            item = Budget(household_id=user.household_id, category_id=category_id, month=month)
            session.add(item)
        item.cents, item.rollover = payload.cents, payload.rollover
        audit(session, user, "budget.set", f"{month}/{category_id}")
        session.commit()
        return {"ok": True}

    @app.post("/api/budgets/{month}/copy")
    def copy_budget(month: str, payload: CopyMonth, user=Depends(current), session=Depends(db)):
        month_value(month)
        month_value(payload.source)
        lock(session, user)
        if session.scalar(
            select(Budget.id).where(Budget.household_id == user.household_id, Budget.month == month)
        ):
            raise HTTPException(409, "Destination already has budgets")
        source = session.scalars(
            select(Budget).where(
                Budget.household_id == user.household_id, Budget.month == payload.source
            )
        ).all()
        if not source:
            raise HTTPException(422, "Source month has no budgets")
        session.add_all(
            [
                Budget(
                    household_id=user.household_id,
                    category_id=b.category_id,
                    month=month,
                    cents=b.cents,
                    rollover=b.rollover,
                )
                for b in source
            ]
        )
        audit(session, user, "budget.copy", month)
        session.commit()
        return {"ok": True}

    def effective_savings(session, user, month):
        latest = {}
        for row in session.scalars(select(Savings).where(
            Savings.household_id == user.household_id, Savings.month <= month,
        ).order_by(Savings.month, Savings.id)):
            latest[row.name] = row
        return latest

    def set_savings(session, user, month, name, cents):
        item = session.scalar(select(Savings).where(
            Savings.household_id == user.household_id,
            Savings.month == month, Savings.name == name,
        ))
        if item is None:
            item = Savings(household_id=user.household_id, month=month, name=name)
            session.add(item)
        item.cents = cents
        session.flush()
        return item

    def active_savings(session, user, month, ident):
        item = owned(session, Savings, ident, user)
        if item.month > month:
            raise HTTPException(404, "Allocation not found")
        latest = effective_savings(session, user, month).get(item.name)
        if latest is None or latest.cents == 0:
            raise HTTPException(404, "Allocation not found")
        if latest.id != ident:
            raise HTTPException(409, "Savings plan changed. Refresh before editing.")
        return item

    @app.put("/api/savings/{month}")
    def savings(month: str, payload: SavingsIn, user=Depends(current), session=Depends(db)):
        month_value(month)
        lock(session, user)
        set_savings(session, user, month, payload.name, payload.cents)
        audit(session, user, "savings.set", month)
        session.commit()
        return {"ok": True}

    @app.put("/api/savings/{month}/{ident}")
    def edit_savings(month: str, ident: int, payload: SavingsIn, user=Depends(current), session=Depends(db)):
        month_value(month)
        lock(session, user)
        item = active_savings(session, user, month, ident)
        if item.name != payload.name:
            duplicate = effective_savings(session, user, month).get(payload.name)
            if duplicate and duplicate.cents > 0:
                raise HTTPException(409, "A savings plan with that name already exists")
            # Stop the old name from this month onward, preserving prior history.
            set_savings(session, user, month, item.name, 0)
        set_savings(session, user, month, payload.name, payload.cents)
        audit(session, user, "savings.edit", ident)
        session.commit()
        return {"ok": True}

    @app.delete("/api/savings/{month}/{ident}")
    def delete_savings(month: str, ident: int, user=Depends(current), session=Depends(db)):
        month_value(month)
        lock(session, user)
        item = active_savings(session, user, month, ident)
        # A zero override prevents an earlier recurring plan from reappearing.
        set_savings(session, user, month, item.name, 0)
        audit(session, user, "savings.delete", ident)
        session.commit()
        return {"ok": True}

    @app.put("/api/plan/{month}")
    def save_plan(month: str, payload: PlanIn, user=Depends(current), session=Depends(db)):
        month_value(month)
        lock(session, user)
        # Validate the whole edit before committing any part of the plan.
        category_ids = [b.category_id for b in payload.budgets]
        saving_ids = [s.id for s in payload.savings if s.id is not None]
        removed = payload.removed_savings
        if (len(set(category_ids)) != len(category_ids)
                or len(set(saving_ids + removed)) != len(saving_ids + removed)):
            raise HTTPException(422, "Duplicate plan entries")
        rows = {ident: active_savings(session, user, month, ident)
                for ident in saving_ids + removed}
        untouched = {name for name, row in effective_savings(session, user, month).items()
                     if row.cents > 0 and row.id not in rows}
        names = [s.name for s in payload.savings]
        if len(set(names)) != len(names) or untouched.intersection(names):
            raise HTTPException(409, "A savings plan with that name already exists")
        for b in payload.budgets:
            owned(session, Category, b.category_id, user)
            item = session.scalar(select(Budget).where(
                Budget.household_id == user.household_id,
                Budget.category_id == b.category_id, Budget.month == month))
            if item is None:
                item = Budget(household_id=user.household_id, category_id=b.category_id, month=month)
                session.add(item)
            item.cents, item.rollover = b.cents, b.rollover
        for row in rows.values():
            set_savings(session, user, month, row.name, 0)
        for saving in payload.savings:
            set_savings(session, user, month, saving.name, saving.cents)
        audit(session, user, "plan.save", month)
        session.commit()
        return {"ok": True}

    @app.get("/api/dashboard")
    def dashboard(month: str, user=Depends(current), session=Depends(db)):
        month_value(month)
        spent = dict(
            session.execute(
                select(Split.category_id, func.sum(Split.cents))
                .join(Transaction, Transaction.id == Split.transaction_id)
                .where(
                    Transaction.household_id == user.household_id,
                    Transaction.kind.in_(SPENDING),
                    Transaction.date >= date.fromisoformat(month + "-01"),
                    Transaction.date < next_month(month),
                )
                .group_by(Split.category_id)
            ).all()
        )
        history = (
            session.execute(
                select(Budget)
                .where(Budget.household_id == user.household_id, Budget.month <= month)
                .order_by(Budget.month)
            )
            .scalars()
            .all()
        )
        # Aggregate category/month spending once, then compute contiguous rollover.
        all_spend = {
            (str(m), c): n
            for m, c, n in session.execute(
                select(
                    func.substr(Transaction.date.cast(String), 1, 7),
                    Split.category_id,
                    func.sum(Split.cents),
                )
                .join(Transaction, Transaction.id == Split.transaction_id)
                .where(
                    Transaction.household_id == user.household_id, Transaction.kind.in_(SPENDING)
                )
                .group_by(func.substr(Transaction.date.cast(String), 1, 7), Split.category_id)
            )
        }
        # Effective plans inherit per category without writing during a GET.
        # Walk every month so rollover includes months nobody opened the app.
        carry, effective, budget_rows = {}, {}, {}
        cursor = history[0].month if history else month
        while cursor <= month:
            for b in history:
                if b.month == cursor:
                    effective[b.category_id] = b
            for category_id, b in effective.items():
                incoming = carry.get(category_id, 0) if b.rollover else 0
                if cursor == month:
                    budget_rows[category_id] = (b, incoming)
                carry[category_id] = (
                    b.cents + incoming - all_spend.get((cursor, category_id), 0)
                    if b.rollover else 0
                )
            cursor = next_month(cursor).isoformat()[:7]
        result = []
        for c in scoped(session, Category, user):
            b, roll = budget_rows.get(c.id, (None, 0))
            amount = b.cents if b else 0
            actual = spent.get(c.id, 0)
            result.append(
                dict(
                    id=c.id,
                    name=c.name,
                    mode=c.mode,
                    archived=c.archived,
                    budget_cents=amount,
                    rollover_cents=roll,
                    rollover=bool(b and b.rollover),
                    configured=bool(b),
                    inherited_from=b.month if b and b.month != month else None,
                    spent_cents=actual,
                    remaining_cents=amount + roll - actual,
                )
            )
        txs = session.scalars(
            select(Transaction).where(
                Transaction.household_id == user.household_id,
                Transaction.date >= date.fromisoformat(month + "-01"),
                Transaction.date < next_month(month),
            )
        ).all()
        plans = [
            dict(id=s.id, name=s.name, cents=s.cents,
                 inherited_from=s.month if s.month != month else None)
            for s in effective_savings(session, user, month).values()
            if s.cents > 0
        ]
        return {
            "month": month,
            "spent_cents": sum(spent.values()),
            "budget_cents": sum(c["budget_cents"] + c["rollover_cents"] for c in result),
            "remaining_cents": sum(c["remaining_cents"] for c in result),
            "review_count": sum(t.kind == "review" for t in txs),
            "income_cents": -sum(t.cents for t in txs if t.kind == "income"),
            "contribution_cents": -sum(t.cents for t in txs if t.kind == "contribution"),
            "categories": result,
            "savings": plans,
            "planned_savings_cents": sum(s["cents"] for s in plans),
        }

    from .banks import register
    register(app, current, db, lock, owned, audit, origin)

    dist = Path(
        os.getenv("FRONTEND_DIST", str(Path(__file__).resolve().parents[2] / "frontend" / "dist"))
    )
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        if (dist / "icons").is_dir():
            app.mount("/icons", StaticFiles(directory=dist / "icons"), name="icons")
        if (dist / "brand").is_dir():
            app.mount("/brand", StaticFiles(directory=dist / "brand"), name="brand")

        def public_app_file(filename, media_type):
            def serve():
                path = dist / filename
                if not path.is_file():
                    raise HTTPException(404, "File not found")
                headers = {"Service-Worker-Allowed": "/"} if filename == "sw.js" else {}
                return FileResponse(path, media_type=media_type, headers=headers)

            return serve

        app.add_api_route(
            "/manifest.webmanifest",
            public_app_file("manifest.webmanifest", "application/manifest+json"),
            methods=["GET"],
            include_in_schema=False,
        )
        app.add_api_route(
            "/sw.js",
            public_app_file("sw.js", "application/javascript"),
            methods=["GET"],
            include_in_schema=False,
        )

        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")

    return app


def next_month(month):
    y, m = map(int, month.split("-"))
    return date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
