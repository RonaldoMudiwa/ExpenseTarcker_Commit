"""Moving transactions in and out of CSV files.

CSV opens in Excel and Google Sheets, so this is how data gets out of the
app for a spreadsheet, or in from one.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .exceptions import ExpenseTrackerError, StorageError
from .factory import TransactionFactory
from .ledger import TransactionLedger

# Every column any transaction type can use. Columns that don't apply to a
# row, like "source" on an expense, are left empty.
COLUMNS = [
    "transaction_id",
    "type",
    "date",
    "amount",
    "description",
    "category",
    "payment_method",
    "source",
    "is_recurring",
]

REQUIRED_COLUMNS = {"type", "date", "amount", "description"}


class CSVExporter:
    """Writes a ledger to a CSV file, one row per transaction."""

    def export(self, ledger: TransactionLedger, path: str | Path) -> int:
        """Write the file and return how many rows were written.

        Raises:
            StorageError: If the file can't be written.
        """
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # newline="" stops Windows adding a blank line between rows.
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=COLUMNS, restval="")
                writer.writeheader()
                for transaction in sorted(ledger):
                    writer.writerow(self._to_row(transaction.to_dict()))
        except OSError as error:
            raise StorageError(f"Could not write {path}: {error}") from error
        return len(ledger)

    @staticmethod
    def _to_row(data: dict[str, Any]) -> dict[str, str]:
        row = {column: data.get(column, "") for column in COLUMNS}
        # Plain "true"/"false" reads better in a spreadsheet than Python's True.
        if isinstance(data.get("is_recurring"), bool):
            row["is_recurring"] = "true" if data["is_recurring"] else "false"
        return row


class CSVImporter:
    """Reads transactions from a CSV file.

    The file needs at least type, date, amount and description columns.
    Rows with no transaction_id get a new one, so a hand made spreadsheet
    can be imported.
    """

    def __init__(self, factory: TransactionFactory | None = None) -> None:
        self._factory = factory or TransactionFactory.default()

    def read(self, path: str | Path) -> TransactionLedger:
        """Return every row as a transaction in a new ledger.

        Nothing is imported if any row is bad. The error names the line, so
        it can be fixed in the spreadsheet.

        Raises:
            StorageError: If the file is missing, has the wrong columns, or
                a row can't be read.
        """
        path = Path(path)
        try:
            # utf-8-sig also copes with the hidden marker Excel adds to the start.
            with path.open(newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                # Headings are matched in any case, so "Date" works as well as "date".
                if reader.fieldnames:
                    reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
                self._check_columns(reader.fieldnames, path)
                ledger = TransactionLedger()
                # Line 1 is the header, so the first row of data is line 2.
                for line_number, row in enumerate(reader, start=2):
                    try:
                        ledger.add(self._factory.from_dict(self._clean(row)))
                    except ExpenseTrackerError as error:
                        raise StorageError(f"{path}, line {line_number}: {error}") from error
        except OSError as error:
            raise StorageError(f"Could not read {path}: {error}") from error
        return ledger

    @staticmethod
    def _check_columns(fieldnames: list[str] | None, path: Path) -> None:
        missing = REQUIRED_COLUMNS - set(fieldnames or [])
        if missing:
            raise StorageError(
                f"{path} is missing these columns: {', '.join(sorted(missing))}."
            )

    @staticmethod
    def _clean(row: dict[str, str | None]) -> dict[str, Any]:
        """Tidy one row into the shape from_dict expects."""
        # Drop empty cells, so the class defaults are used instead.
        data: dict[str, Any] = {
            key: value.strip()
            for key, value in row.items()
            if key and value and value.strip()
        }
        if "type" in data:
            data["type"] = data["type"].lower()
        if "is_recurring" in data:
            data["is_recurring"] = data["is_recurring"].lower() in {"true", "yes", "1"}
        return data
