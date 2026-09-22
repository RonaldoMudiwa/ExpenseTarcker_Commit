"""Personal Expense Tracker.

A small, well structured Python application for recording and analysing
personal spending. Built over one week as project 1 of a 12 week portfolio,
with every object oriented principle applied deliberately rather than
decoratively.

This file is the package's front door. Importing the handful of names that
callers actually need means user code can write::

    from expense_tracker import Expense, Income, TransactionLedger

instead of reaching into module paths that may be reorganised later. The
``__all__`` list states the public API explicitly, so everything not on it
is understood to be internal.
"""

from .enums import Category, IncomeSource, PaymentMethod
from .exceptions import (
    DuplicateTransactionError,
    ExpenseTrackerError,
    LedgerError,
    SerializationError,
    TransactionNotFoundError,
    ValidationError,
)
from .expense import Expense
from .income import Income
from .ledger import TransactionLedger
from .transaction import Transaction

__version__ = "0.2.0"

__all__ = [
    # Enums
    "Category",
    "PaymentMethod",
    "IncomeSource",
    # Domain model
    "Transaction",
    "Expense",
    "Income",
    "TransactionLedger",
    # Exceptions
    "ExpenseTrackerError",
    "ValidationError",
    "SerializationError",
    "LedgerError",
    "DuplicateTransactionError",
    "TransactionNotFoundError",
    "__version__",
]
