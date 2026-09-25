"""Personal Expense Tracker.

A command line tool for recording and analysing personal spending. Project 1
of a 12 week portfolio.

This file is the package's front door. Importing the handful of names callers
actually need lets user code write:

    from expense_tracker import Expense, Income, TransactionLedger

instead of reaching into module paths that might move later. Anything not in
__all__ is internal.
"""

from .enums import Category, IncomeSource, PaymentMethod
from .exceptions import (
    DuplicateTransactionError,
    ExpenseTrackerError,
    LedgerError,
    SerializationError,
    StorageError,
    TransactionNotFoundError,
    ValidationError,
)
from .expense import Expense
from .factory import TransactionFactory
from .income import Income
from .ledger import TransactionLedger
from .repository import (
    InMemoryTransactionRepository,
    JSONTransactionRepository,
    TransactionRepository,
)
from .transaction import Transaction

__version__ = "0.3.0"

__all__ = [
    # Enums
    "Category",
    "PaymentMethod",
    "IncomeSource",
    # Model
    "Transaction",
    "Expense",
    "Income",
    "TransactionLedger",
    # Storage
    "TransactionFactory",
    "TransactionRepository",
    "JSONTransactionRepository",
    "InMemoryTransactionRepository",
    # Errors
    "ExpenseTrackerError",
    "ValidationError",
    "SerializationError",
    "StorageError",
    "LedgerError",
    "DuplicateTransactionError",
    "TransactionNotFoundError",
    "__version__",
]
