from conftest import classify, imported, items
from household.models import Audit, Session
from sqlalchemy import select

CSV = "date,merchant,amount,external_id\n2026-11-01,Market,100.25,a\n2026-11-02,Card payment,-100.25,b\n2026-11-03,Refund,-20.00,c\n"


def test_security(env):
    c, app = env
    assert c.get("/api/me").json()["members"] == ["One", "Two"]
    with app.state.factory() as db:
        assert db.scalar(select(Session)).token_hash != c.cookies.get("hh_session")
    token = c.headers.pop("X-CSRF-Token")
    assert c.post("/api/accounts", json={"name": "x", "kind": "credit"}).status_code == 403
    c.headers["X-CSRF-Token"] = token
    assert (
        c.post(
            "/api/accounts",
            headers={"Origin": "https://evil.example"},
            json={"name": "x", "kind": "credit"},
        ).status_code
        == 403
    )
    assert c.post("/plaid/exchange_token/", json={}).status_code == 404
    assert c.get("/analytics/dashboard/1").status_code == 404
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/accounts").status_code == 401


def test_isolation(env):
    c, _ = env
    assert len(c.get("/api/accounts").json()) == 2
    assert c.post("/api/imports/preview", json={"account_id": 3, "csv": CSV}).status_code == 404
    imported(c, CSV)
    tx = items(c)[-1]
    assert classify(c, tx, splits=[{"category_id": 3, "cents": tx["cents"]}]).status_code == 404
    assert c.put("/api/budgets/2026-11/3", json={"cents": 100}).status_code == 404
    r = c.post(
        "/api/auth/login", json={"email": "other@example.com", "password": "a safe test password"}
    )
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    assert items(c) == []
    assert classify(c, tx).status_code == 404
    assert c.post("/api/imports/1/commit", json={"expected_net_cents": 0}).status_code == 404


def test_financial_types(env):
    c, _ = env
    imported(c, CSV)
    d = c.get("/api/dashboard?month=2026-11").json()
    assert d["spent_cents"] == 0 and d["review_count"] == 3
    kinds = {"Market": "expense", "Card payment": "card_payment", "Refund": "refund"}
    for tx in items(c):
        assert classify(c, tx, kinds[tx["merchant"]]).status_code == 200
    assert c.get("/api/dashboard?month=2026-11").json()["spent_cents"] == 8025
    imported(
        c,
        "date,merchant,amount\n2026-11-04,Contribution,-200\n2026-11-05,Salary,-300\n2026-11-06,Loan,40\n2026-11-07,Savings,50\n2026-11-08,Transfer,60\n2026-11-09,Reimbursement,-10\n",
        2,
    )
    kinds = {
        "Contribution": "contribution",
        "Salary": "income",
        "Loan": "loan_payment",
        "Savings": "savings",
        "Transfer": "transfer",
        "Reimbursement": "reimbursement",
    }
    for tx in items(c):
        if tx["merchant"] in kinds:
            assert classify(c, tx, kinds[tx["merchant"]]).status_code == 200
    d = c.get("/api/dashboard?month=2026-11").json()
    assert (d["spent_cents"], d["income_cents"], d["contribution_cents"]) == (11025, 30000, 20000)


def test_import_reconciliation_duplicates(env):
    c, _ = env
    csv = "date,merchant,amount\n2026-11-01,Coffee,5.10\n2026-11-01,Coffee,5.10\n"
    assert imported(c, csv) == {"imported": 2, "duplicates": 0}
    assert imported(c, csv) == {"imported": 0, "duplicates": 2}
    p = c.post("/api/imports/preview", json={"account_id": 1, "csv": CSV}).json()
    assert (
        c.post(f"/api/imports/{p['id']}/commit", json={"expected_net_cents": 1}).status_code == 422
    )
    assert len(items(c)) == 2
    assert (
        c.post(
            f"/api/imports/{p['id']}/commit", json={"expected_net_cents": p["net_cents"]}
        ).status_code
        == 200
    )
    assert (
        c.post(
            f"/api/imports/{p['id']}/commit", json={"expected_net_cents": p["net_cents"]}
        ).status_code
        == 409
    )
    assert (
        c.post(
            "/api/imports/preview",
            json={"account_id": 1, "csv": CSV.replace("100.25,a", "101.25,a")},
        ).status_code
        == 409
    )


def test_splits_bulk_atomicity_concurrency(env):
    c, app = env
    imported(c, "date,merchant,amount\n2026-11-01,Market,10.01\n2026-11-02,Store,5\n")
    a, b = items(c)
    assert classify(c, a, splits=[{"category_id": 1, "cents": 100}]).status_code == 422
    assert (
        classify(
            c, a, splits=[{"category_id": 1, "cents": -100}, {"category_id": 2, "cents": 600}]
        ).status_code
        == 422
    )
    assert (
        classify(
            c, a, splits=[{"category_id": 1, "cents": 200}, {"category_id": 2, "cents": 300}]
        ).status_code
        == 200
    )
    assert classify(c, a).status_code == 409
    assert (
        c.post(
            "/api/transactions/bulk",
            json={
                "transactions": {str(b["id"]): b["version"], str(a["id"]): a["version"]},
                "kind": "expense",
                "category_id": 1,
            },
        ).status_code
        == 409
    )
    assert next(t for t in items(c) if t["id"] == b["id"])["kind"] == "review"
    assert classify(c, b, "income", []).status_code == 422
    assert (
        c.post(
            "/api/transactions/bulk",
            json={
                "transactions": {str(b["id"]): b["version"]},
                "kind": "expense",
                "category_id": 2,
            },
        ).status_code
        == 200
    )
    d = c.get("/api/dashboard?month=2026-11").json()
    assert d["spent_cents"] == 1501 and d["categories"][1]["spent_cents"] == 1301
    with app.state.factory() as db:
        assert db.scalar(select(Audit.id))


def test_rollover_inheritance_and_savings(env):
    c, _ = env
    for month in ["2026-09", "2026-10", "2026-11"]:
        assert (
            c.put(f"/api/budgets/{month}/1", json={"cents": 10000, "rollover": True}).status_code
            == 200
        )
    imported(
        c, "date,merchant,amount\n2026-09-03,Shop,150\n2026-10-03,Shop,10\n2026-11-03,Shop,5\n"
    )
    for month in ["2026-09", "2026-10", "2026-11"]:
        for tx in items(c, month):
            assert classify(c, tx).status_code == 200
    d = c.get("/api/dashboard?month=2026-11").json()
    assert d["categories"][0]["rollover_cents"] == 4000 and d["remaining_cents"] == 13500
    c.put("/api/savings/2026-11", json={"name": "Travel", "cents": 25000})
    d = c.get("/api/dashboard?month=2026-11").json()
    assert d["remaining_cents"] == 13500 and d["planned_savings_cents"] == 25000
    assert c.post("/api/budgets/2026-12/copy", json={"source": "2026-11"}).status_code == 200
    assert c.post("/api/budgets/2026-12/copy", json={"source": "2026-11"}).status_code == 409
    c.put("/api/budgets/2027-02/1", json={"cents": 10000, "rollover": True})
    assert c.get("/api/dashboard?month=2027-02").json()["categories"][0]["rollover_cents"] == 33500


def test_filters_validation(env):
    c, _ = env
    imported(c, CSV)
    assert c.get("/api/transactions?month=2026-11&search=MARKET").json()["total"] == 1
    assert c.get("/api/transactions?month=2026-11&search=%25").json()["total"] == 0
    assert len(c.get("/api/transactions?month=2026-11&limit=1&offset=1").json()["items"]) == 1
    assert c.get("/api/dashboard?month=2026-13").status_code == 422
    assert c.get("/api/transactions?month=2026-11&limit=1000").status_code == 422
    assert c.put("/api/budgets/2026-11/1", json={"cents": 1.5}).status_code == 422
    assert c.put("/api/budgets/2026-11/1", json={"cents": -1}).status_code == 422
    assert c.post("/api/accounts", json={"name": "Card", "kind": "credit"}).status_code == 409


def test_members_and_throttle(env):
    c, _ = env
    imported(c, CSV)
    r = c.post(
        "/api/auth/login", json={"email": "two@example.com", "password": "a safe test password"}
    )
    assert r.status_code == 200
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    assert len(items(c)) == 3
    for _ in range(20):
        r = c.post("/api/auth/login", json={"email": "bad@example.com", "password": "bad"})
    assert r.status_code == 429


def test_recurring_budgets_override_zero_and_read_only(env):
    c, app = env
    c.put('/api/budgets/2026-09/1', json={'cents': 10000, 'rollover': True})
    c.put('/api/budgets/2026-11/2', json={'cents': 5000, 'rollover': False})
    d = c.get('/api/dashboard?month=2026-12').json()
    assert d['categories'][0]['budget_cents'] == 10000
    assert d['categories'][0]['rollover_cents'] == 30000
    assert d['categories'][0]['inherited_from'] == '2026-09'
    assert d['categories'][1]['budget_cents'] == 5000
    c.put('/api/budgets/2026-11/1', json={'cents': 0, 'rollover': False})
    d = c.get('/api/dashboard?month=2026-12').json()
    assert d['categories'][0]['budget_cents'] == 0
    assert d['categories'][0]['rollover_cents'] == 0
    assert c.get('/api/dashboard?month=2026-08').json()['budget_cents'] == 0
    from household.models import Budget
    with app.state.factory() as db:
        assert len(db.scalars(select(Budget)).all()) == 3  # GET never materializes plans


def test_savings_edit_delete_scope_and_conflicts(env):
    c, app = env
    c.put('/api/savings/2026-11', json={'name': 'Travel', 'cents': 20000})
    c.put('/api/savings/2026-11', json={'name': 'House', 'cents': 10000})
    goal = c.get('/api/dashboard?month=2026-11').json()['savings'][0]
    path = f"/api/savings/2026-11/{goal['id']}"
    assert c.put(path, json={'name': 'House', 'cents': 100}).status_code == 409
    assert c.put(path, json={'name': 'Holiday', 'cents': 30000}).status_code == 200
    d = c.get('/api/dashboard?month=2026-11').json()
    assert d['planned_savings_cents'] == 40000 and d['spent_cents'] == 0
    assert c.delete(path.replace('2026-11', '2026-12')).status_code == 404
    from household.models import Savings
    with app.state.factory() as db:
        other = Savings(household_id=2, name='Private', month='2026-11', cents=100)
        db.add(other)
        db.commit()
        private_id = other.id
    private = f'/api/savings/2026-11/{private_id}'
    assert c.put(private, json={'name': 'Stolen', 'cents': 0}).status_code == 404
    assert c.delete(private).status_code == 404
    assert c.delete(path).status_code == 200
    assert c.delete(path).status_code == 404
    assert c.get('/api/dashboard?month=2026-11').json()['planned_savings_cents'] == 10000


def test_transaction_sorting_before_pagination(env):
    c, _ = env
    imported(c, 'date,merchant,amount\n2026-11-01,Big,100\n2026-11-03,Small,10\n2026-11-02,Return,-20\n')
    for tx in items(c):
        classify(c, tx, kind='refund' if tx['cents'] < 0 else 'expense')
    def names(**params):
        r = c.get('/api/transactions', params={'month': '2026-11', 'category_id': 1, **params})
        assert r.status_code == 200
        return [t['merchant'] for t in r.json()['items']]
    assert names() == ['Small', 'Return', 'Big']
    assert names(sort='oldest') == ['Big', 'Return', 'Small']
    assert names(sort='largest') == ['Big', 'Small', 'Return']
    assert names(sort='smallest') == ['Return', 'Small', 'Big']
    assert names(sort='largest', credits_first=True, limit=1) == ['Return']
    assert names(search='Big', credits_first=True) == ['Big']
    assert c.get('/api/transactions?month=2026-11&sort=invalid').status_code == 422
