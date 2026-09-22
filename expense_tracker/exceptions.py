"""The exception hierarchy for the whole package.

Why define our own exceptions at all, when ``ValueError`` already exists?

* **Catchability.** Every error this package raises inherits from one base
  class, so a caller can write ``except ExpenseTrackerError`` and catch
  everything we raise without also swallowing unrelated bugs from the
  standard library.
* **Meaning.** ``TransactionNotFoundError`` says far more at a call site
  than ``KeyError`` does, and it lets the command line interface (Day 6)
  print a sensible message per error type instead of one generic apology.
* **Stability.** The internals can change how a failure is detected without
  changing the exception the caller has been told to expect.

The hierarchy is deliberately shallow. Depth in an exception tree is only
worth paying for when callers genuinely need to catch at different levels.

    ExpenseTrackerError
    ├── ValidationError
    ├── SerializationError
    └── LedgerError
        ├── DuplicateTransactionError
        └── TransactionNotFoundError
"""

from __future__ import annotations


class ExpenseTrackerError(Exception):
    """Base class for every error raised by this package.

    Nothing raises this directly. It exists so that callers have a single
    name to catch, which is the standard convention for a Python library.
    """


class ValidationError(ExpenseTrackerError):
    """Raised when a value would put a domain object into an invalid state.

    Examples: a negative amount, an empty description, an unknown category.

    The domain object validates itself rather than trusting the caller. That
    is the whole point of encapsulation: an object should never be able to
    exist in an invalid state.
    """


class SerializationError(ExpenseTrackerError):
    """Raised when a dictionary cannot be turned back into a domain object.

    Used by the ``from_dict`` factory methods when a required key is missing
    or holds a value of the wrong shape.
    """


class LedgerError(ExpenseTrackerError):
    """Base class for problems with the *collection* of transactions.

    Separated from ``ValidationError`` on purpose. A validation failure is
    about one object being wrong in itself; a ledger error is about an
    otherwise valid object being wrong *for this collection*, such as
    adding the same transaction twice.
    """


class DuplicateTransactionError(LedgerError):
    """Raised when a transaction already present in the ledger is added again.

    The ledger indexes transactions by their identifier, so silently
    accepting a duplicate would either double count the money or quietly
    discard an entry. Both are worse than a loud failure.
    """


class TransactionNotFoundError(LedgerError):
    """Raised when a lookup or removal names an identifier the ledger lacks.

    Chosen over the built in ``KeyError`` because the ledger is a domain
    object, not a dictionary, and its callers should not have to know that a
    dictionary happens to be the storage used underneath.
    """
