"""Core domain models: users, accounts, transactions, payee rules.

Stub schema reflecting the README's data model. Columns are illustrative; the
goal is a real shape to build against, not a finalized migration.
"""
import enum

from sqlalchemy import Boolean, Column, Date, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.app.db.database import Base


class Role(str, enum.Enum):
    owner = "owner"
    bookkeeper = "bookkeeper"
    viewer = "viewer"


class TxnType(str, enum.Enum):
    personal = "personal"
    business = "business"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)  # bcrypt
    role = Column(Enum(Role), nullable=False, default=Role.viewer)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    nickname = Column(String, nullable=False)  # e.g. "Business Checking"
    institution = Column(String)
    transactions = relationship("Transaction", back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    # Bank-provided FITID; the dedup key across overlapping QFX exports.
    fitid = Column(String, index=True, nullable=False)
    posted = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    payee = Column(String)
    memo = Column(String)
    txn_type = Column(Enum(TxnType))           # personal / business (null = untagged)
    schedule_c_category = Column(String)        # set when txn_type == business

    account = relationship("Account", back_populates="transactions")


class PayeeRule(Base):
    """Learned auto-tagging rule: a payee pattern -> tag + category."""

    __tablename__ = "payee_rules"

    id = Column(Integer, primary_key=True)
    pattern = Column(String, nullable=False)    # payee name pattern
    txn_type = Column(Enum(TxnType), nullable=False)
    schedule_c_category = Column(String)
    enabled = Column(Boolean, default=True)
