"""Request/response schemas for the REST API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.models import Role, TxnType


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
    passphrase: str = Field(min_length=8)
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

    model_config = ConfigDict(from_attributes=True)


class TagRequest(BaseModel):
    txn_type: TxnType
    schedule_c_category: Optional[str] = None
