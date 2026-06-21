"""Request/response schemas for the REST API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.models import Role, TxnType

QuarterlyMethod = Literal["set_aside", "se_income", "safe_harbor"]
FilingStatus = Literal["single", "married_joint", "married_separate", "head_of_household"]


# --- Setup / unlock -------------------------------------------------------

class SetupStatus(BaseModel):
    initialized: bool   # an encrypted database exists
    unlocked: bool      # the database is open this process


class FirstAccount(BaseModel):
    nickname: str
    institution: Optional[str] = None
    account_number: Optional[str] = None


class SetupRequest(BaseModel):
    owner_username: str = Field(min_length=1)
    owner_password: str = Field(min_length=8)
    # Required for the local SQLCipher store; ignored for external databases
    # (PostgreSQL), which need no passphrase. Validated in the setup handler.
    passphrase: Optional[str] = None
    ledger_name: str = Field(min_length=1)
    first_account: Optional[FirstAccount] = None


class UnlockRequest(BaseModel):
    passphrase: str = Field(min_length=1)


# --- Auth -----------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Users ----------------------------------------------------------------

class UserCreate(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    role: Role


class UserUpdate(BaseModel):
    """Partial update: change a user's role and/or reset their password."""
    role: Optional[Role] = None
    password: Optional[str] = Field(default=None, min_length=8)


class UserOut(BaseModel):
    id: int
    username: str
    role: Role

    model_config = ConfigDict(from_attributes=True)


# --- Accounts -------------------------------------------------------------

class AccountCreate(BaseModel):
    nickname: str = Field(min_length=1)
    institution: Optional[str] = None
    account_number: Optional[str] = None


class AccountUpdate(BaseModel):
    """Partial update; only supplied fields are changed."""
    nickname: Optional[str] = Field(default=None, min_length=1)
    institution: Optional[str] = None
    account_number: Optional[str] = None


class AccountOut(BaseModel):
    id: int
    nickname: str
    institution: Optional[str] = None
    account_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Transactions ---------------------------------------------------------

class ImportResult(BaseModel):
    parsed: int       # transactions read from the file
    imported: int     # new transactions written
    duplicates: int   # skipped because the FITID already existed
    auto_tagged: int = 0  # imported rows auto-tagged from learned payee rules


class TransactionOut(BaseModel):
    id: int
    account_id: int
    fitid: str
    posted: date
    amount: Decimal
    payee: Optional[str] = None
    memo: Optional[str] = None
    txn_type: Optional[TxnType] = None
    schedule_c_category: Optional[str] = None
    personal_category: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TagRequest(BaseModel):
    txn_type: TxnType
    schedule_c_category: Optional[str] = None
    personal_category: Optional[str] = None


# --- Reports --------------------------------------------------------------

class CategoryAmount(BaseModel):
    category: str
    amount: Decimal


class PnLReport(BaseModel):
    start: Optional[date] = None
    end: Optional[date] = None
    income: Decimal
    expenses: Decimal
    net: Decimal
    by_category: list[CategoryAmount]


class ScheduleCSummary(BaseModel):
    year: int
    gross_receipts: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    by_category: list[CategoryAmount]


class YearSummary(BaseModel):
    year: int
    income: Decimal
    expenses: Decimal
    net: Decimal


class YearOverYear(BaseModel):
    years: list[YearSummary]


class QuarterlyEstimate(BaseModel):
    method: str
    net_profit: float
    annual: float
    per_quarter: float
    detail: dict[str, object]


class RecurringSeries(BaseModel):
    payee: str
    amount: Decimal
    occurrences: int
    cadence: str
    average_gap_days: float
    last_seen: date


# --- Ledger settings ------------------------------------------------------

class LedgerSettings(BaseModel):
    """Owner-configurable ledger settings (stored as key/value Setting rows)."""
    name: Optional[str] = None   # company / ledger name (stored as "ledger_name")
    ein: Optional[str] = None
    fiscal_year_start: int = 1  # 1 = January (calendar year)
    quarterly_method: QuarterlyMethod = "set_aside"
    quarterly_set_aside_rate: float = 0.27   # fraction of net profit to set aside
    quarterly_filing_status: FilingStatus = "single"
    quarterly_prior_year_tax: float = 0.0


class LedgerSettingsUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    ein: Optional[str] = None
    fiscal_year_start: Optional[int] = Field(default=None, ge=1, le=12)
    quarterly_method: Optional[QuarterlyMethod] = None
    quarterly_set_aside_rate: Optional[float] = Field(default=None, ge=0, le=1)
    quarterly_filing_status: Optional[FilingStatus] = None
    quarterly_prior_year_tax: Optional[float] = Field(default=None, ge=0)
