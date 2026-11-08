from datetime import date

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select

from household import banks
from household.models import BankItem, BankLink, Transaction


@pytest.fixture
def bank_env(env, monkeypatch):
    for key, value in {"PLAID_CLIENT_ID": "test-client", "PLAID_SECRET": "test-secret", "PLAID_ENV": "sandbox", "BANK_TOKEN_KEY": Fernet.generate_key().decode()}.items():
        monkeypatch.setenv(key, value)
    return env


def test_link_is_user_scoped_encrypted_and_selective(bank_env, monkeypatch):
    c, app = bank_env
    def fake(path, data):
        if path == "/link/token/create":
            assert data["products"] == ["transactions"]
            return {"hosted_link_url": "https://secure.plaid.com/hl/test", "link_token": "secret-link-token"}
        if path == "/link/token/get":
            return {"link_sessions": [{"results": {"item_add_results": [{"public_token": "public-test"}]}}]}
        if path == "/item/public_token/exchange":
            return {"item_id": "item-1", "access_token": "secret-access-token"}
        if path == "/accounts/get":
            return {"accounts": [{"account_id": "a", "name": "Joint", "type": "credit", "mask": "1234", "balances": {"iso_currency_code": "USD"}}]}
        raise AssertionError(path)
    monkeypatch.setattr(banks, "call", fake)
    assert c.post("/api/banks/link").status_code == 200
    ident = c.get("/api/banks").json()["pending_link"]
    with app.state.factory() as s:
        assert "secret-link-token" not in s.get(BankLink, ident).token
    assert c.post(f"/api/banks/finish/{ident}").status_code == 200
    state = c.get("/api/banks").json()
    assert "secret-access-token" not in str(state)
    assert state["items"][0]["selected"] == []
    assert c.put("/api/banks/1/accounts", json={"account_ids": ["wrong"], "start_date": str(date.today())}).status_code == 422
    assert c.put("/api/banks/1/accounts", json={"account_ids": ["a"], "start_date": str(date.today())}).status_code == 200
    with app.state.factory() as s:
        assert "secret-access-token" not in s.get(BankItem, 1).token
    assert c.post("/api/banks/999/sync").status_code == 404


def test_sync_cutoff_dedup_and_atomic_cursor(bank_env, monkeypatch):
    c, app = bank_env
    with app.state.factory() as s:
        item = BankItem(household_id=1, provider_id="provider", token=banks.cipher().encrypt(b"token").decode(), accounts=[], account_map={"a": 1}, start_date=date.today())
        s.add(item)
        s.commit()
    tx = {"account_id": "a", "transaction_id": "t1", "date": str(date.today()), "amount": 12.34, "iso_currency_code": "USD", "name": "Shop"}
    monkeypatch.setattr(banks, "call", lambda *args: {"added": [tx, dict(tx, transaction_id="old", date="2000-01-01"), dict(tx, transaction_id="pending", pending=True), dict(tx, transaction_id="private", account_id="private")], "next_cursor": "cursor1", "has_more": False})
    assert c.post("/api/banks/1/sync").json()["changed"] == 1
    with app.state.factory() as s:
        item = s.get(BankItem, 1)
        item.last_sync = None
        s.commit()
    assert c.post("/api/banks/1/sync").json()["changed"] == 0
    with app.state.factory() as s:
        assert len(s.scalars(select(Transaction).where(Transaction.source == "plaid")).all()) == 1
        s.get(BankItem, 1).last_sync = None
        s.commit()
    def broken(path, data):
        if data["cursor"] == "cursor1":
            return {"added": [dict(tx, transaction_id="new")], "next_cursor": "middle", "has_more": True}
        raise HTTPException(502, "Plaid: TEST_ERROR")
    monkeypatch.setattr(banks, "call", broken)
    assert c.post("/api/banks/1/sync").status_code == 502
    with app.state.factory() as s:
        assert s.get(BankItem, 1).cursor == "cursor1"
        assert len(s.scalars(select(Transaction).where(Transaction.source == "plaid")).all()) == 1


def test_disconnect_revokes_token_and_preserves_transactions(bank_env, monkeypatch):
    c, app = bank_env
    with app.state.factory() as s:
        s.add(BankItem(household_id=1, provider_id="one", token=banks.cipher().encrypt(b"token").decode(), accounts=[], account_map={"a": 1}, start_date=date.today()))
        s.add(BankItem(household_id=2, provider_id="other", token=banks.cipher().encrypt(b"other-token").decode(), accounts=[], account_map={}))
        s.commit()
    calls = []
    monkeypatch.setattr(banks, "call", lambda path, data: calls.append(path) or {})
    assert c.post("/api/banks/2/disconnect").status_code == 404
    assert c.post("/api/banks/1/disconnect").status_code == 200
    assert calls == ["/item/remove"]
    assert c.get("/api/banks").json()["items"] == []
    with app.state.factory() as s:
        assert s.get(BankItem, 1).token == ""
