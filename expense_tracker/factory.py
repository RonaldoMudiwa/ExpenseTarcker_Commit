"""Rebuilds the right kind of transaction from saved data."""

from __future__ import annotations

from typing import Any, Mapping

from .exceptions import SerializationError
from .expense import Expense
from .income import Income
from .transaction import Transaction


class TransactionFactory:
    """Turns a saved record back into an Expense, Income, and so on.

    Each record has a "type" key. The factory looks it up and passes the
    record to the matching class. New types are added with register().
    """

    def __init__(self) -> None:
        # "expense" -> Expense, "income" -> Income
        self._classes: dict[str, type[Transaction]] = {}

    @classmethod
    def default(cls) -> "TransactionFactory":
        """A factory that already knows Expense and Income."""
        factory = cls()
        factory.register(Expense)
        factory.register(Income)
        return factory

    def register(self, transaction_class: type[Transaction]) -> None:
        """Add a transaction class. Raises ValueError if its type is taken."""
        tag = transaction_class.TRANSACTION_TYPE
        if tag in self._classes:
            raise ValueError(f"Type {tag!r} is already registered.")
        self._classes[tag] = transaction_class

    @property
    def known_types(self) -> tuple[str, ...]:
        return tuple(self._classes)

    def from_dict(self, data: Mapping[str, Any]) -> Transaction:
        """Build a transaction from a saved record.

        Raises:
            SerializationError: If the record isn't a dict, or its type is
                missing or unknown.
        """
        if not isinstance(data, Mapping):
            raise SerializationError(
                f"Each record must be a dictionary, got {type(data).__name__}."
            )

        tag = data.get("type")
        if tag is None:
            raise SerializationError("Record is missing its 'type' key.")

        transaction_class = self._classes.get(tag)
        if transaction_class is None:
            allowed = ", ".join(self._classes)
            raise SerializationError(
                f"Unknown transaction type {tag!r}. Known types: {allowed}."
            )

        return transaction_class.from_dict(data)
