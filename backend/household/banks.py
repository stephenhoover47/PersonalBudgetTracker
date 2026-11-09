"""Plaid live pilot. Never expose credentials or raw provider responses to clients."""
import hashlib
import json
import os
import time
from datetime import date
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from .models import Account, BankItem, BankLink, Split, Transaction


def configured():
    return all(os.getenv(k) for k in ("PLAID_CLIENT_ID", "PLAID_SECRET", "BANK_TOKEN_KEY")) and os.getenv("PLAID_ENV") in {"sandbox", "production"}


def cipher():
    if not configured():
        raise HTTPException(503, "Bank connection configuration is incomplete")
    return Fernet(os.environ["BANK_TOKEN_KEY"].encode())


def call(path, data):
    cipher()
    payload = dict(data, client_id=os.environ["PLAID_CLIENT_ID"], secret=os.environ["PLAID_SECRET"])
    req = Request("https://" + os.environ["PLAID_ENV"] + ".plaid.com" + path,
                  data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Plaid-Version": "2020-09-14"})
    try:
        with urlopen(req, timeout=25) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            code = json.load(exc).get("error_code", "PROVIDER_ERROR")
        except (ValueError, AttributeError):
            code = "PROVIDER_ERROR"
        # Return only an error code, never messages, tokens, requests or responses.
        safe = code if isinstance(code, str) and code.replace("_", "").isalnum() else "PROVIDER_ERROR"
        raise HTTPException(502, "Plaid: " + safe) from None
    except (URLError, TimeoutError):
        raise HTTPException(502, "Plaid is temporarily unavailable; try again later") from None


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_ids: list[str] = Field(min_length=1, max_length=30)
    start_date: date


def sync_item(session, item):
    if not item.token:
        raise HTTPException(409, "Bank connection has been disconnected")
    if not item.account_map or not item.start_date:
        raise HTTPException(409, "Choose household accounts and a start date first")
    cursor = item.cursor
    pages = []
    for _ in range(10):
        page = call("/transactions/sync", {"access_token": cipher().decrypt(item.token.encode()).decode(), "cursor": cursor or "", "count": 500})
        pages.append(page)
        cursor = page["next_cursor"]
        if not page["has_more"]:
            break
    else:
        raise HTTPException(502, "Sync exceeded its page limit; no changes were saved")
    changed = 0
    for page in pages:
        for tx in page.get("added", []) + page.get("modified", []):
            account_id = item.account_map.get(tx["account_id"])
            if not account_id:
                continue
            fingerprint = hashlib.sha256(("plaid:" + tx["transaction_id"]).encode()).hexdigest()
            existing = session.scalar(select(Transaction).where(Transaction.account_id == account_id, Transaction.fingerprint == fingerprint))
            amount = int((Decimal(str(tx["amount"])) * 100).quantize(Decimal("1")))
            eligible = not tx.get("pending") and tx.get("iso_currency_code") == "USD" and date.fromisoformat(tx["date"]) >= item.start_date and amount != 0
            if not eligible:
                if existing:
                    session.execute(delete(Split).where(Split.transaction_id == existing.id))
                    session.delete(existing)
                continue
            merchant = (tx.get("merchant_name") or tx.get("name") or "Bank transaction")[:200]
            when = date.fromisoformat(tx["date"])
            if existing and (existing.cents, existing.date, existing.merchant) == (amount, when, merchant):
                continue
            if existing:
                session.execute(delete(Split).where(Split.transaction_id == existing.id))
                existing.cents, existing.date, existing.merchant = amount, when, merchant
                existing.kind = "review"
                existing.version += 1
            else:
                session.add(Transaction(household_id=item.household_id, account_id=account_id, date=when, merchant=merchant, cents=amount, kind="review", fingerprint=fingerprint, source="plaid", external_id=tx["transaction_id"]))
            session.flush()
            changed += 1
        for removed in page.get("removed", []):
            for account_id in item.account_map.values():
                tx = session.scalar(select(Transaction).where(Transaction.account_id == account_id, Transaction.source == "plaid", Transaction.external_id == removed["transaction_id"]))
                if tx:
                    session.execute(delete(Split).where(Split.transaction_id == tx.id))
                    session.delete(tx)
                    changed += 1
    item.cursor, item.last_sync = cursor, int(time.time())
    return changed


class LinkStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date = date(2026, 11, 1)


def public_tokens(result):
    tokens = set()
    for session in result.get("link_sessions", []):
        for item in (session.get("results") or {}).get("item_add_results", []):
            if item.get("public_token"):
                tokens.add(item["public_token"])
        legacy = session.get("on_success") or {}
        if legacy.get("public_token"):
            tokens.add(legacy["public_token"])
    return tokens



def link_diagnostics(result):
    """Allowlist support metadata; never return credentials, account data or messages."""
    def fields(obj, names):
        return {key: value[:160] for key in names
                if isinstance(value := obj.get(key), str) and value}

    sessions = []
    for item in result.get("link_sessions", [])[-10:]:
        summary = fields(item, ("link_session_id", "started_at", "finished_at"))
        exit_data = item.get("exit") or item.get("on_exit") or {}
        summary["exit"] = fields(exit_data.get("metadata") or {}, ("status", "request_id", "link_session_id"))
        summary["error"] = fields(exit_data.get("error") or {}, ("error_code", "error_type"))
        summary["events"] = []
        for event in item.get("events", [])[-100:]:
            clean = fields(event, ("event_name", "timestamp"))
            clean.update(fields(event.get("event_metadata") or {},
                                ("exit_status", "error_code", "error_type", "request_id", "institution_id", "view_name")))
            summary["events"].append(clean)
        sessions.append(summary)
    return {"request_id": fields(result, ("request_id",)).get("request_id"), "sessions": sessions}


def register(app, current, db, lock, owned, audit, origin):
    @app.get("/api/banks")
    def status(user=Depends(current), session=Depends(db)):
        items = session.scalars(select(BankItem).where(BankItem.household_id == user.household_id, BankItem.token != "")).all()
        pending = session.scalar(select(BankLink.id).where(BankLink.user_id == user.id, BankLink.completed.is_(False), BankLink.created > int(time.time()) - 21600).order_by(BankLink.id.desc()))
        return {"configured": configured(), "pending_link": pending, "pending_links": [link.id for link in session.scalars(select(BankLink).where(BankLink.user_id == user.id, BankLink.completed.is_(False), BankLink.created > int(time.time()) - 21600).order_by(BankLink.id))], "items": [dict(id=i.id, accounts=i.accounts, selected=list(i.account_map), start_date=i.start_date, last_sync=i.last_sync) for i in items]}

    @app.post("/api/banks/link")
    def begin(payload: LinkStart = LinkStart(), user=Depends(current), session=Depends(db)):
        cipher()
        if payload.start_date > date.today() or (date.today() - payload.start_date).days > 90:
            raise HTTPException(422, "Choose a date within the past 90 days")
        lock(session, user)
        recent = session.scalar(select(BankLink).where(BankLink.user_id == user.id, BankLink.created > int(time.time()) - 60))
        if recent:
            raise HTTPException(429, "Wait one minute before starting another connection")
        result = call("/link/token/create", {"user": {"client_user_id": str(user.id)}, "client_name": "PocketWatcher", "products": ["transactions"], "country_codes": ["US"], "language": "en", "transactions": {"days_requested": 90}, "hosted_link": {"completion_redirect_uri": origin + "/?bank_link=complete"}})
        url = result["hosted_link_url"]
        if urlparse(url).scheme != "https" or urlparse(url).hostname != "secure.plaid.com":
            raise HTTPException(502, "Unexpected Plaid link destination")
        session.add(BankLink(household_id=user.household_id, user_id=user.id, token=cipher().encrypt(result["link_token"].encode()).decode(), created=int(time.time()), start_date=payload.start_date))
        audit(session, user, "bank.link", "started")
        session.commit()
        return {"url": url}

    @app.post("/api/banks/diagnostics/{ident}")
    def diagnostics(ident: int, user=Depends(current), session=Depends(db)):
        link = owned(session, BankLink, ident, user)
        if link.user_id != user.id or link.completed or link.created < int(time.time()) - 21600:
            raise HTTPException(404, "Link diagnostics are no longer available")
        result = call("/link/token/get", {"link_token": cipher().decrypt(link.token.encode()).decode()})
        return link_diagnostics(result)

    @app.post("/api/banks/finish/{ident}")
    def finish(ident: int, user=Depends(current), session=Depends(db)):
        lock(session, user)
        link = owned(session, BankLink, ident, user)
        if link.user_id != user.id or link.created < int(time.time()) - 21600:
            raise HTTPException(404, "Link session expired")
        if link.completed:
            return {"ok": True}
        def close_unusable(exc):
            if exc.status_code != 502 or exc.detail not in {"Plaid: INVALID_PUBLIC_TOKEN", "Plaid: INVALID_LINK_TOKEN"}:
                raise exc
            # Terminal one-use/expired credentials must not block newer sessions.
            # Keep a non-secret failure marker; never discard a saved BankItem.
            link.completed = True
            link.token = "failed:" + exc.detail.split(": ", 1)[1]
            audit(session, user, "bank.link_unusable", ident)
            session.commit()
            return {"ok": False, "retry_required": True}
        try:
            result = call("/link/token/get", {"link_token": cipher().decrypt(link.token.encode()).decode()})
        except HTTPException as exc:
            return close_unusable(exc)
        tokens = public_tokens(result)
        if not tokens:
            raise HTTPException(409, "No completed bank connection yet. Finish Plaid, then try again.")
        if len(tokens) != 1:
            raise HTTPException(409, "Use one bank connection per Link session")
        try:
            exchanged = call("/item/public_token/exchange", {"public_token": next(iter(tokens))})
        except HTTPException as exc:
            return close_unusable(exc)
        item = BankItem(household_id=user.household_id, provider_id=exchanged["item_id"], token=cipher().encrypt(exchanged["access_token"].encode()).decode(), accounts=[], account_map={}, start_date=link.start_date)
        session.add(item)
        link.completed = True
        link.token = ""
        audit(session, user, "bank.link", "completed")
        # Persist the durable token before the next external request. Public tokens are single-use.
        session.commit()
        discover_accounts(session, item)
        session.commit()
        return {"ok": True}

    @app.post("/api/banks/recover")
    def recover(user=Depends(current), session=Depends(db)):
        ids = list(session.scalars(select(BankLink.id).where(BankLink.user_id == user.id, BankLink.completed.is_(False), BankLink.created > int(time.time()) - 21600).order_by(BankLink.id)))
        completed, expired = 0, 0
        for ident in ids:
            try:
                result = finish(ident, user, session)
                if result.get("retry_required"):
                    expired += 1
                else:
                    completed += 1
            except HTTPException as exc:
                session.rollback()
                if exc.status_code != 409:
                    raise
        return {"completed": completed, "pending": len(ids) - completed - expired, "expired": expired}

    def discover_accounts(session, item):
        accounts = call("/accounts/get", {"access_token": cipher().decrypt(item.token.encode()).decode()})["accounts"]
        item.accounts = [dict(id=a["account_id"], name=a["name"], mask=a.get("mask"), kind="credit" if a["type"] == "credit" else "savings" if a.get("subtype") == "savings" else "checking") for a in accounts if a["type"] in {"credit", "depository"} and a.get("balances", {}).get("iso_currency_code") == "USD"]

    @app.post("/api/banks/{ident}/discover")
    def discover(ident: int, user=Depends(current), session=Depends(db)):
        lock(session, user)
        item = owned(session, BankItem, ident, user)
        discover_accounts(session, item)
        session.commit()
        return {"ok": True}

    @app.put("/api/banks/{ident}/accounts")
    def choose(ident: int, payload: Selection, user=Depends(current), session=Depends(db)):
        lock(session, user)
        item = owned(session, BankItem, ident, user)
        if item.account_map:
            raise HTTPException(409, "Accounts already selected for this connection")
        if payload.start_date > date.today() or (date.today() - payload.start_date).days > 90:
            raise HTTPException(422, "Choose a date within the past 90 days")
        choices = {a["id"]: a for a in item.accounts}
        if not set(payload.account_ids) <= choices.keys():
            raise HTTPException(422, "Invalid account selection")
        mapping = {}
        for aid in set(payload.account_ids):
            a = choices[aid]
            account = Account(household_id=user.household_id, name=f"{a['name'][:65]} • {a.get('mask') or 'linked'} ({item.id}-{len(mapping)+1})", kind=a["kind"])
            session.add(account)
            session.flush()
            mapping[aid] = account.id
        item.account_map, item.start_date = mapping, payload.start_date
        audit(session, user, "bank.accounts", ident)
        session.commit()
        return {"ok": True}

    @app.post("/api/banks/{ident}/disconnect")
    def disconnect(ident: int, user=Depends(current), session=Depends(db)):
        lock(session, user)
        item = owned(session, BankItem, ident, user)
        if item.token:
            call("/item/remove", {"access_token": cipher().decrypt(item.token.encode()).decode()})
            item.token = ""
        audit(session, user, "bank.disconnect", ident)
        session.commit()
        return {"ok": True}

    @app.post("/api/banks/{ident}/sync")
    def sync(ident: int, user=Depends(current), session=Depends(db)):
        lock(session, user)
        item = owned(session, BankItem, ident, user)
        if item.last_sync and item.last_sync > int(time.time()) - 60:
            raise HTTPException(429, "Wait one minute between syncs")
        changed = sync_item(session, item)
        audit(session, user, "bank.sync", ident)
        session.commit()
        return {"changed": changed}
