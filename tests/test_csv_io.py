"""Tests for CSV import and export."""

from __future__ import annotations

import csv
import io
from decimal import Decimal

import pytest

from expense_tracker import (
    Category,
    CSVExporter,
    CSVImporter,
    Expense,
    Income,
    IncomeSource,
    InMemoryTransactionRepository,
    PaymentMethod,
    StorageError,
    TransactionLedger,
)
from expense_tracker.cli import main


@pytest.fixture
def ledger() -> TransactionLedger:
    return TransactionLedger(
        [
            Expense("62.35", "Weekly shop, Tesco", Category.GROCERIES, "2026-09-03",
                    PaymentMethod.DEBIT_CARD),
            Income("2400.00", "Salary", IncomeSource.SALARY, "2026-09-01",
                   is_recurring=True),
            Expense("3.40", 'Coffee "to go"', Category.EATING_OUT, "2026-09-08"),
        ]
    )


@pytest.fixture
def csv_path(tmp_path):
    return tmp_path / "transactions.csv"


def write_csv(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def read_rows(path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


class TestExport:

    def test_returns_row_count(self, ledger, csv_path):
        assert CSVExporter().export(ledger, csv_path) == 3

    def test_has_header_and_one_row_each(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        assert len(read_rows(csv_path)) == 3

    def test_sorted_by_date(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        dates = [row["date"] for row in read_rows(csv_path)]
        assert dates == sorted(dates)

    def test_amounts_keep_two_decimal_places(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        assert read_rows(csv_path)[0]["amount"] == "2400.00"

    def test_unused_columns_are_blank(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        salary = read_rows(csv_path)[0]
        assert salary["category"] == "" and salary["source"] == "salary"

    def test_recurring_written_as_text(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        assert read_rows(csv_path)[0]["is_recurring"] == "true"

    def test_commas_and_quotes_survive(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        descriptions = {row["description"] for row in read_rows(csv_path)}
        assert "Weekly shop, Tesco" in descriptions
        assert 'Coffee "to go"' in descriptions

    def test_creates_missing_folders(self, ledger, tmp_path):
        path = tmp_path / "exports" / "sept.csv"
        CSVExporter().export(ledger, path)
        assert path.exists()

    def test_empty_ledger_writes_just_the_header(self, csv_path):
        CSVExporter().export(TransactionLedger(), csv_path)
        assert csv_path.read_text(encoding="utf-8").count("\n") == 1


class TestRoundTrip:
    """Export then import must give back the same transactions."""

    def test_same_transactions(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        assert set(CSVImporter().read(csv_path)) == set(ledger)

    def test_every_field_survives(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        loaded = {t.description: t for t in CSVImporter().read(csv_path)}
        shop = loaded["Weekly shop, Tesco"]
        assert shop.amount == Decimal("62.35")
        assert shop.category is Category.GROCERIES
        assert shop.payment_method is PaymentMethod.DEBIT_CARD
        assert loaded["Salary"].is_recurring is True

    def test_balance_is_exact(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        assert CSVImporter().read(csv_path).balance == ledger.balance


class TestImportHandMadeFiles:
    """Files typed up in a spreadsheet, not made by the exporter."""

    def test_minimum_columns(self, csv_path):
        write_csv(csv_path, "type,date,amount,description\nexpense,2026-10-01,5,Lunch\n")
        expense = CSVImporter().read(csv_path)[0]
        assert expense.category is Category.OTHER

    def test_new_ids_are_made(self, csv_path):
        write_csv(csv_path, "type,date,amount,description\n"
                            "expense,2026-10-01,5,Lunch\nexpense,2026-10-01,5,Lunch\n")
        loaded = CSVImporter().read(csv_path)
        assert len(loaded) == 2

    def test_headings_in_any_case(self, csv_path):
        write_csv(csv_path, "Type,Date,Amount,Description\nExpense,2026-10-01,5,Lunch\n")
        assert len(CSVImporter().read(csv_path)) == 1

    def test_excel_start_marker(self, csv_path):
        csv_path.write_bytes(b"\xef\xbb\xbftype,date,amount,description\n"
                             b"income,2026-10-01,50,Gift\n")
        assert isinstance(CSVImporter().read(csv_path)[0], Income)

    def test_friendly_category_names(self, csv_path):
        write_csv(csv_path, "type,date,amount,description,category\n"
                            "expense,2026-10-01,5,Lunch,Eating Out\n")
        assert CSVImporter().read(csv_path)[0].category is Category.EATING_OUT

    @pytest.mark.parametrize("cell, expected", [
        ("true", True), ("yes", True), ("1", True), ("TRUE", True),
        ("false", False), ("no", False), ("", False),
    ])
    def test_recurring_values(self, csv_path, cell, expected):
        write_csv(csv_path, "type,date,amount,description,is_recurring\n"
                            f"income,2026-10-01,50,Pay,{cell}\n")
        assert CSVImporter().read(csv_path)[0].is_recurring is expected

    def test_spaces_around_values_are_trimmed(self, csv_path):
        write_csv(csv_path, "type,date,amount,description\n"
                            " expense , 2026-10-01 , 5.00 , Lunch \n")
        assert CSVImporter().read(csv_path)[0].amount == Decimal("5.00")


class TestBadFiles:

    def test_missing_file(self, tmp_path):
        with pytest.raises(StorageError, match="Could not read"):
            CSVImporter().read(tmp_path / "nope.csv")

    def test_missing_columns_are_named(self, csv_path):
        write_csv(csv_path, "date,amount\n2026-10-01,5\n")
        with pytest.raises(StorageError, match="description, type"):
            CSVImporter().read(csv_path)

    def test_empty_file(self, csv_path):
        write_csv(csv_path, "")
        with pytest.raises(StorageError, match="missing these columns"):
            CSVImporter().read(csv_path)

    def test_bad_row_names_the_line(self, csv_path):
        write_csv(csv_path, "type,date,amount,description\n"
                            "expense,2026-10-01,5,Lunch\nexpense,2026-10-02,-1,Oops\n")
        with pytest.raises(StorageError, match="line 3"):
            CSVImporter().read(csv_path)

    def test_unknown_type(self, csv_path):
        write_csv(csv_path, "type,date,amount,description\nloan,2026-10-01,5,x\n")
        with pytest.raises(StorageError, match="line 2"):
            CSVImporter().read(csv_path)

    def test_bad_date(self, csv_path):
        write_csv(csv_path, "type,date,amount,description\nexpense,01/10/2026,5,x\n")
        with pytest.raises(StorageError):
            CSVImporter().read(csv_path)


class TestCommands:
    """export and import through the command line."""

    def run(self, repository, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = main(list(argv), repository=repository, out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    def test_export_with_filter(self, tmp_path):
        repo = InMemoryTransactionRepository()
        self.run(repo, "demo")
        path = tmp_path / "groceries.csv"
        code, out, _ = self.run(repo, "export", str(path), "--category", "groceries")
        assert code == 0 and "Exported 2" in out
        assert len(read_rows(path)) == 2

    def test_import_into_empty(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        repo = InMemoryTransactionRepository()
        code, out, _ = self.run(repo, "import", str(csv_path))
        assert code == 0 and "Imported 3" in out
        assert len(repo.load()) == 3

    def test_import_twice_is_refused(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        repo = InMemoryTransactionRepository()
        self.run(repo, "import", str(csv_path))
        code, _, err = self.run(repo, "import", str(csv_path))
        assert code == 1 and "--skip-duplicates" in err
        assert len(repo.load()) == 3

    def test_skip_duplicates(self, ledger, csv_path):
        CSVExporter().export(ledger, csv_path)
        repo = InMemoryTransactionRepository()
        self.run(repo, "import", str(csv_path))
        code, out, _ = self.run(repo, "import", str(csv_path), "--skip-duplicates")
        assert code == 0 and "skipped 3" in out
        assert len(repo.load()) == 3

    def test_failed_import_changes_nothing(self, csv_path):
        write_csv(csv_path, "type,date,amount,description\n"
                            "expense,2026-10-01,5,Lunch\nexpense,2026-10-02,-1,Oops\n")
        repo = InMemoryTransactionRepository()
        code, _, _ = self.run(repo, "import", str(csv_path))
        assert code == 1 and len(repo.load()) == 0
