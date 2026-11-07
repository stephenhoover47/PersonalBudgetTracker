import pytest
from household.ingestion import money, parse_csv


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1.001", "1e999", "bad", "10000000.01"])
def test_invalid_money(value):
    with pytest.raises(ValueError):
        money(value)


@pytest.mark.parametrize(
    "value,expected", [("1.01", 101), ("-2.05", -205), ("$1,234.56", 123456), ("0.10", 10)]
)
def test_money(value, expected):
    assert money(value) == expected


def test_adapters():
    rows = parse_csv(
        "Transaction Date,Description,Amount\n11/01/2026,Market,-12.01\n11/02/2026,Payment,12.01\n",
        "chase",
    )
    assert [r["cents"] for r in rows] == [1201, -1201]
    rows = parse_csv(
        "Transaction Date,Description,Debit,Credit\n2026-11-01,Market,12.01,\n2026-11-02,Payment,,12.01\n",
        "capital_one",
    )
    assert [r["cents"] for r in rows] == [1201, -1201]
    assert (
        parse_csv("date,merchant,amount\n2026-11-01,Market,-12.01\n", outflows_positive=False)[0][
            "cents"
        ]
        == 1201
    )


@pytest.mark.parametrize(
    "csv",
    [
        "date,merchant,amount\n2026-02-30,A,1\n",
        "date,merchant,amount\n2026-11-01,A,0\n",
        "date,merchant,amount\n2026-11-01,,1\n",
        "date,merchant,amount\n2026-11-01,A,1,extra\n",
        "date,merchant,amount\n2026-11-01,A\n",
        "date,merchant,amount,external_id\n2026-11-01,A,1,id\n2026-11-02,B,2,id\n",
        "date,merchant,amount,amount\n2026-11-01,A,1,2\n",
        "bad\n",
    ],
)
def test_bad_csv(csv):
    with pytest.raises(ValueError):
        parse_csv(csv)
