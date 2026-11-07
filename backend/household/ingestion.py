"""Posted USD CSV adapter. Future aggregators should emit these normalized rows.

Never infer spending from merchant text. Financial classification is a separate review.
"""

import csv
import hashlib
import io
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation


def money(value):
    try:
        number = Decimal(value.strip().replace(",", "").replace("$", ""))
        if (
            not number.is_finite()
            or number != number.quantize(Decimal(".01"))
            or abs(number) > 10000000
        ):
            raise ValueError()
        return int(number * 100)
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError("Amount must be finite USD with at most two decimal places")


def parse_csv(content, format="canonical", outflows_positive=True):
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), strict=True)
    required = {
        "canonical": {"date", "merchant", "amount"},
        "chase": {"Transaction Date", "Description", "Amount"},
        "capital_one": {"Transaction Date", "Description", "Debit", "Credit"},
    }[format]
    if (
        not reader.fieldnames
        or not required.issubset(reader.fieldnames)
        or len(set(reader.fieldnames)) != len(reader.fieldnames)
    ):
        raise ValueError(
            "Missing or duplicate CSV headers. Required: " + ", ".join(sorted(required))
        )
    rows, occurrences = [], Counter()
    for line, row in enumerate(reader, 2):
        if line > 5001:
            raise ValueError("Limit is 5,000 rows per import")
        try:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Malformed CSV row")
            raw_date = row["date"] if format == "canonical" else row["Transaction Date"]
            parsed = None
            for pattern in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    parsed = datetime.strptime(raw_date.strip(), pattern).date()
                    break
                except ValueError:
                    pass
            if parsed is None or not 2000 <= parsed.year <= 2100:
                raise ValueError("Invalid posted date")
            merchant = " ".join(
                (row["merchant"] if format == "canonical" else row["Description"]).split()
            )
            if not merchant or len(merchant) > 200:
                raise ValueError("Merchant must have 1–200 characters")
            if format == "capital_one":
                debit, credit = row["Debit"].strip(), row["Credit"].strip()
                if bool(debit) == bool(credit):
                    raise ValueError("Exactly one of Debit/Credit must be populated")
                cents = money(debit) if debit else -money(credit)
                if (debit and cents < 0) or (credit and cents > 0):
                    raise ValueError("Debit/Credit values must be positive")
            else:
                cents = money(row["amount"] if format == "canonical" else row["Amount"])
                if format == "chase" or not outflows_positive:
                    cents = -cents
            if not cents:
                raise ValueError("Zero amounts are not transactions")
            external = row.get("external_id", "").strip()
            if len(external) > 200:
                raise ValueError("external_id too long")
            # Multiset occurrence preserves two legitimate identical purchases.
            # Stable external IDs reconcile changed descriptions across exports.
            base = f"{parsed}|{merchant.casefold()}|{cents}"
            occurrences[base] += 1
            identity = "id:" + external if external else f"row:{base}|{occurrences[base]}"
            fingerprint = hashlib.sha256(identity.encode()).hexdigest()
            rows.append(
                dict(
                    date=parsed.isoformat(),
                    merchant=merchant,
                    cents=cents,
                    external_id=external or None,
                    fingerprint=fingerprint,
                )
            )
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Row {line}: {exc}") from exc
    if not rows:
        raise ValueError("CSV contains no transactions")
    if len({r["fingerprint"] for r in rows}) != len(rows):
        raise ValueError("Repeated external_id within file")
    return rows
