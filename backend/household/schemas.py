from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal[
    "review",
    "expense",
    "refund",
    "reimbursement",
    "income",
    "contribution",
    "transfer",
    "card_payment",
    "savings",
    "loan_payment",
]
Cents = int


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class AccountIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["checking", "credit", "savings"]


class CategoryIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    mode: Literal["fixed", "flexible"] = "flexible"


class Allocation(Strict):
    category_id: int = Field(gt=0)
    cents: int = Field(strict=True, ge=-1000000000, le=1000000000)


class Edit(Strict):
    version: int = Field(gt=0)
    kind: Kind
    splits: list[Allocation] = Field(default_factory=list, max_length=30)


class Bulk(Strict):
    transactions: dict[int, int] = Field(min_length=1, max_length=200)
    kind: Kind
    category_id: int | None = None


class BudgetIn(Strict):
    cents: int = Field(strict=True, ge=0, le=1000000000)
    rollover: bool = False


class SavingsIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    cents: int = Field(strict=True, ge=0, le=1000000000)


class ImportIn(Strict):
    account_id: int
    csv: str = Field(max_length=2000000)
    format: Literal["canonical", "chase", "capital_one"] = "canonical"
    outflows_positive: bool = True


class CommitImport(Strict):
    expected_net_cents: int = Field(strict=True)


class CopyMonth(Strict):
    source: str
