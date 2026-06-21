"""Core domain models: settings, users, accounts, transactions, payee rules."""
import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from backend.app.db.database import Base


class Role(str, enum.Enum):
    owner = "owner"
    bookkeeper = "bookkeeper"
    viewer = "viewer"


class TxnType(str, enum.Enum):
    personal = "personal"
    business = "business"


class Setting(Base):
    """Key/value store for install-level metadata (ledger name, JWT secret)."""

    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)  # bcrypt
    role = Column(Enum(Role), nullable=False, default=Role.viewer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    nickname = Column(String, nullable=False)  # e.g. "Business Checking"
    institution = Column(String)
    # Bank's account identifier from the QFX file, used to route imports.
    account_number = Column(String, index=True)
    transactions = relationship("Transaction", back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"
    # The dedup guarantee: a given bank FITID can exist once per account, so
    # overlapping QFX export windows can be imported freely.
    __table_args__ = (
        UniqueConstraint("account_id", "fitid", name="uq_account_fitid"),
    )

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    fitid = Column(String, index=True, nullable=False)  # bank-provided FITID
    posted = Column(Date, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    payee = Column(String)
    memo = Column(String)
    txn_type = Column(Enum(TxnType))          # personal / business (null = untagged)
    schedule_c_category = Column(String)       # set when txn_type == business
    personal_category = Column(String)         # set when txn_type == personal

    account = relationship("Account", back_populates="transactions")


class PayeeRule(Base):
    """Learned auto-tagging rule: a payee pattern -> tag + category."""

    __tablename__ = "payee_rules"

    id = Column(Integer, primary_key=True)
    pattern = Column(String, nullable=False)   # payee name pattern
    txn_type = Column(Enum(TxnType), nullable=False)
    schedule_c_category = Column(String)
    enabled = Column(Boolean, default=True)
