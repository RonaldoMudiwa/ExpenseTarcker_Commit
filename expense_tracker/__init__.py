"""Personal Expense Tracker.

Record and analyse personal spending. Everything most code needs can be
imported straight from here:

    from expense_tracker import Expense, Income, TransactionLedger
"""

from .csv_io import CSVExporter, CSVImporter
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
from .filters import (
    AmountRangeFilter,
    CategoryFilter,
    DateRangeFilter,
    IncomeSourceFilter,
    MatchAll,
    TextSearchFilter,
    TransactionFilter,
    TypeFilter,
    all_of,
)
from .income import Income
from .ledger import TransactionLedger
from .reports import (
    Budget,
    BudgetStatus,
    MonthSummary,
    ReportFormatter,
    ReportGenerator,
)
from .repository import (
    InMemoryTransactionRepository,
    JSONTransactionRepository,
    TransactionRepository,
)
from .transaction import Transaction

__version__ = "1.0.0"

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
    # Filters
    "TransactionFilter",
    "DateRangeFilter",
    "CategoryFilter",
    "IncomeSourceFilter",
    "TypeFilter",
    "AmountRangeFilter",
    "TextSearchFilter",
    "MatchAll",
    "all_of",
    # CSV
    "CSVExporter",
    "CSVImporter",
    # Reports
    "ReportGenerator",
    "ReportFormatter",
    "Budget",
    "BudgetStatus",
    "MonthSummary",
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
