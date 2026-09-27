"""All the errors this package can raise.

Everything inherits from ExpenseTrackerError, so one except clause catches
the lot without also swallowing unrelated bugs.

    ExpenseTrackerError
    |-- ValidationError
    |-- SerializationError
    |-- StorageError
    |-- LedgerError
        |-- DuplicateTransactionError
        |-- TransactionNotFoundError
"""

from __future__ import annotations


class ExpenseTrackerError(Exception):
    """Base class for every error in this package. Never raised directly."""


class ValidationError(ExpenseTrackerError):
    """A value isn't allowed, e.g. a negative amount or a blank description."""


class SerializationError(ExpenseTrackerError):
    """Stored data can't be turned back into an object, usually a missing key."""


class StorageError(ExpenseTrackerError):
    """Saving or loading failed, e.g. the file isn't valid JSON."""


class LedgerError(ExpenseTrackerError):
    """A problem with the ledger rather than with one transaction."""


class DuplicateTransactionError(LedgerError):
    """This transaction is already in the ledger."""


class TransactionNotFoundError(LedgerError):
    """No transaction in the ledger has that id."""
