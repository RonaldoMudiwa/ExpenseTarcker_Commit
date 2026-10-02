"""Tests for the command line interface.

Each test runs main() with an in-memory repository and captures what is
printed, so nothing touches the real data file.
"""

from __future__ import annotations

import io
from decimal import Decimal

import pytest

from expense_tracker import Expense, InMemoryTransactionRepository, TransactionLedger
from expense_tracker.cli import main, parse_month, sample_transactions
from expense_tracker.exceptions import ValidationError


class Runner:
    """Runs commands against one shared in-memory repository."""

    def __init__(self) -> None:
        self.repository = InMemoryTransactionRepository()

    def __call__(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        code = main(list(argv), repository=self.repository, out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    @property
    def ledger(self) -> TransactionLedger:
        return self.repository.load()


@pytest.fixture
def run() -> Runner:
    return Runner()


@pytest.fixture
def demo(run) -> Runner:
    run("demo")
    return run


class TestAdding:

    def test_add_expense(self, run):
        code, out, _ = run("add-expense", "3.40", "Flat white", "-c", "eating out",
                           "-d", "2026-09-08", "-m", "cash")
        assert code == 0
        assert "Flat white" in out
        expense = run.ledger[0]
        assert isinstance(expense, Expense)
        assert expense.amount == Decimal("3.40")

    def test_add_income_recurring(self, run):
        run("add-income", "2400", "Salary", "-s", "salary", "--recurring")
        assert run.ledger[0].is_recurring is True

    def test_defaults_to_other(self, run):
        run("add-expense", "1", "Something")
        assert run.ledger[0].category.value == "other"

    def test_bad_amount_is_an_error_not_a_crash(self, run):
        code, _, err = run("add-expense", "-5", "Oops")
        assert code == 1
        assert err.startswith("Error:")
        assert len(run.ledger) == 0

    def test_bad_category(self, run):
        code, _, err = run("add-expense", "5", "Oops", "-c", "yachts")
        assert code == 1 and "yachts" in err


class TestRemove:

    def test_remove_by_short_id(self, demo):
        short_id = demo.ledger[0].transaction_id[:8]
        code, out, _ = demo("remove", short_id)
        assert code == 0 and "Removed" in out
        assert len(demo.ledger) == len(sample_transactions()) - 1

    def test_unknown_id(self, demo):
        code, _, err = demo("remove", "zzzz")
        assert code == 1 and "zzzz" in err


class TestList:

    def test_empty(self, run):
        assert "No transactions" in run("list")[1]

    def test_everything(self, demo):
        lines = demo("list")[1].strip().splitlines()
        assert len(lines) == len(sample_transactions())

    def test_shows_short_id(self, demo):
        first_line = demo("list")[1].splitlines()[0]
        assert len(first_line.split()[0]) == 8

    def test_sorted_by_date(self, demo):
        dates = [line.split()[1] for line in demo("list")[1].splitlines()]
        assert dates == sorted(dates)

    def test_category_filter(self, demo):
        out = demo("list", "--category", "groceries")[1]
        assert out.count("Groceries") == 2 and "Rent" not in out

    def test_filters_combine(self, demo):
        out = demo("list", "--category", "groceries", "--min", "50")[1]
        assert "Weekly shop" in out and "Big shop" not in out

    def test_search(self, demo):
        assert "Rent" in demo("list", "--search", "RENT")[1]

    def test_type(self, demo):
        assert demo("list", "--type", "income")[1].count("+£") == 3

    def test_date_range(self, demo):
        out = demo("list", "--from", "2026-09-10", "--to", "2026-09-17")[1]
        assert len(out.strip().splitlines()) == 2

    def test_month_with_no_data(self, demo):
        assert "No transactions" in demo("list", "--month", "2025-01")[1]

    def test_bad_month(self, demo):
        code, _, err = demo("list", "--month", "Sept")
        assert code == 1 and "2026-09" in err


class TestSummaryAndReports:

    def test_summary(self, demo):
        assert "Balance" in demo("summary")[1]

    def test_summary_respects_filters(self, demo):
        assert "0 in" in demo("summary", "--type", "expense")[1]

    @pytest.mark.parametrize("kind, expected", [
        ("categories", "Housing"),
        ("sources", "Salary"),
        ("monthly", "2026-09"),
    ])
    def test_reports(self, demo, kind, expected):
        code, out, _ = demo("report", kind)
        assert code == 0 and expected in out

    def test_unknown_report_kind(self, demo):
        with pytest.raises(SystemExit):
            demo("report", "weather")


class TestBudget:

    def test_budget(self, demo):
        code, out, _ = demo("budget", "2026-09", "--limit", "groceries=100",
                            "--limit", "eating out=3")
        assert code == 0
        assert out.count("OVER") == 2

    def test_limit_needs_equals_sign(self, demo):
        code, _, err = demo("budget", "2026-09", "--limit", "groceries")
        assert code == 1 and "groceries=250" in err

    def test_limit_is_required(self, demo):
        with pytest.raises(SystemExit):
            demo("budget", "2026-09")


class TestDemo:

    def test_fills_an_empty_file(self, run):
        code, out, _ = run("demo")
        assert code == 0 and len(run.ledger) == len(sample_transactions())

    def test_refuses_to_add_twice(self, demo):
        code, _, err = demo("demo")
        assert code == 1 and "--force" in err

    def test_force(self, demo):
        demo("demo", "--force")
        assert len(demo.ledger) == 2 * len(sample_transactions())


class TestJsonFile:
    """One run against a real file, to prove the default wiring works."""

    def test_uses_the_file_option(self, tmp_path):
        data_file = tmp_path / "mine.json"
        out = io.StringIO()
        assert main(["--file", str(data_file), "add-expense", "2", "Tea"], out=out) == 0
        assert data_file.exists()


class TestParseMonth:

    def test_valid(self):
        assert parse_month("2026-09") == (2026, 9)

    @pytest.mark.parametrize("bad", ["2026", "2026-13", "09-2026x", "Sept"])
    def test_invalid(self, bad):
        with pytest.raises(ValidationError):
            parse_month(bad)


def test_no_command_shows_usage():
    with pytest.raises(SystemExit):
        main([])


def test_runs_as_a_module(tmp_path):
    """python -m expense_tracker should work the same way it does for a user."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "expense_tracker", "--file", str(tmp_path / "t.json"), "summary"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Ledger is empty" in result.stdout
