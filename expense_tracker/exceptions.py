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
    """A value would leave an object in a broken state.

    A negative amount, a blank description, a category that doesn't exist.
    """


class SerializationError(ExpenseTrackerError):
    """Stored data can't be turned back into an object, usually a missing key."""


class StorageError(ExpenseTrackerError):
    """Saving or loading failed, e.g. the file isn't valid JSON."""


class LedgerError(ExpenseTrackerError):
    """Something is wrong with the collection rather than one transaction.

    The transaction itself may be perfectly valid. It just doesn't belong
    here, or isn't here at all.
    """


class DuplicateTransactionError(LedgerError):
    """This transaction is already in the ledger.

    Accepting it would either double count the money or quietly drop one of
    the two. Failing loudly beats both.
    """


class TransactionNotFoundError(LedgerError):
    """No transaction in the ledger has that id.

    Raised instead of KeyError so callers don't need to know a dict is doing
    the work underneath.
    """
