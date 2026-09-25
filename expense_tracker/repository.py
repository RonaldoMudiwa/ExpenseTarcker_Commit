"""Saving and loading transactions.

The rest of the app only uses TransactionRepository, so the JSON file
could be swapped for a database later without changing anything else.
"""

from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .exceptions import ExpenseTrackerError, StorageError
from .factory import TransactionFactory
from .ledger import TransactionLedger

# Change this if the file layout ever changes.
FILE_FORMAT_VERSION = 1


class TransactionRepository(ABC):
    """Anything that can load and save a ledger."""

    @abstractmethod
    def load(self) -> TransactionLedger:
        """Return the saved transactions. Raises StorageError on bad data."""

    @abstractmethod
    def save(self, ledger: TransactionLedger) -> None:
        """Replace the saved data with this ledger. Raises StorageError on failure."""


class InMemoryTransactionRepository(TransactionRepository):
    """Keeps data in memory instead of a file. Used in tests."""

    def __init__(self, factory: TransactionFactory | None = None) -> None:
        self._factory = factory or TransactionFactory.default()
        # Stored as plain dicts, like a real file would be, so editing a
        # transaction after saving doesn't change the saved copy.
        self._records: list[dict[str, Any]] = []

    def load(self) -> TransactionLedger:
        return TransactionLedger(self._factory.from_dict(r) for r in self._records)

    def save(self, ledger: TransactionLedger) -> None:
        self._records = ledger.to_dicts()


class JSONTransactionRepository(TransactionRepository):
    """Saves transactions to a JSON file.

    File layout: {"version": 1, "transactions": [ ... ]}
    """

    def __init__(
        self,
        file_path: str | Path,
        factory: TransactionFactory | None = None,
    ) -> None:
        # The file doesn't need to exist yet.
        self._path = Path(file_path)
        self._factory = factory or TransactionFactory.default()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> TransactionLedger:
        """Read the file. No file yet just means an empty ledger."""
        if not self._path.exists():
            return TransactionLedger()

        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as error:
            raise StorageError(f"Could not read {self._path}: {error}") from error

        try:
            document = json.loads(text)
        except json.JSONDecodeError as error:
            raise StorageError(
                f"{self._path} is not valid JSON (line {error.lineno})."
            ) from error

        records = self._unwrap(document)

        try:
            return TransactionLedger(self._factory.from_dict(r) for r in records)
        except ExpenseTrackerError as error:
            # One error type for the caller, with the real cause kept.
            raise StorageError(f"{self._path} contains a bad record: {error}") from error

    def _unwrap(self, document: Any) -> list[Any]:
        """Check the outer shape of the file and return the records."""
        if not isinstance(document, dict):
            raise StorageError(f"{self._path} should hold a JSON object at the top.")

        version = document.get("version")
        if version != FILE_FORMAT_VERSION:
            raise StorageError(
                f"{self._path} is format version {version!r}; "
                f"this program reads version {FILE_FORMAT_VERSION}."
            )

        records = document.get("transactions")
        if not isinstance(records, list):
            raise StorageError(f"{self._path} has no 'transactions' list.")
        return records

    def save(self, ledger: TransactionLedger) -> None:
        """Write the whole ledger to the file."""
        document = {
            "version": FILE_FORMAT_VERSION,
            "transactions": ledger.to_dicts(),
        }
        text = json.dumps(document, indent=2, ensure_ascii=False)

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._write_safely(text)
        except OSError as error:
            raise StorageError(f"Could not save to {self._path}: {error}") from error

    def _write_safely(self, text: str) -> None:
        """Write to a temp file, then swap it in.

        If the program crashes mid save, the old file is still whole.
        """
        # Same folder, because os.replace only swaps cleanly on one drive.
        handle, temp_name = tempfile.mkstemp(
            dir=self._path.parent, prefix=".tmp_", suffix=".json"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as temp_file:
                temp_file.write(text)
            os.replace(temp_name, self._path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self._path)!r})"
