"""Tests for reports and budgets."""

from __future__ import annotations

from decimal import Decimal

import pytest

from expense_tracker import (
    Budget,
    BudgetStatus,
    Category,
    Expense,
    Income,
    IncomeSource,
    MonthSummary,
    ReportFormatter,
    ReportGenerator,
    TransactionLedger,
    ValidationError,
)


@pytest.fixture
def ledger() -> TransactionLedger:
    return TransactionLedger(
        [
            Income("2400.00", "August salary", IncomeSource.SALARY, "2026-08-01",
                   is_recurring=True),
            Expense("850.00", "August rent", Category.HOUSING, "2026-08-02"),
            Expense("40.00", "Shop", Category.GROCERIES, "2026-08-10"),
            Income("2400.00", "September salary", IncomeSource.SALARY, "2026-09-01",
                   is_recurring=True),
            Income("30.00", "Refund", IncomeSource.REFUND, "2026-09-05"),
            Expense("875.00", "Rent", Category.HOUSING, "2026-09-02"),
            Expense("62.35", "Weekly shop", Category.GROCERIES, "2026-09-03"),
            Expense("20.00", "Top up shop", Category.GROCERIES, "2026-09-20"),
            Expense("75.50", "Dinner out", Category.EATING_OUT, "2026-09-12"),
        ]
    )


@pytest.fixture
def report(ledger) -> ReportGenerator:
    return ReportGenerator(ledger)


class TestSpendingByCategory:

    def test_totals_per_category(self, report):
        totals = report.spending_by_category()
        assert totals[Category.HOUSING] == Decimal("1725.00")
        assert totals[Category.GROCERIES] == Decimal("122.35")
        assert totals[Category.EATING_OUT] == Decimal("75.50")

    def test_biggest_first(self, report):
        assert list(report.spending_by_category())[0] is Category.HOUSING

    def test_categories_with_no_spending_are_left_out(self, report):
        assert Category.HEALTH not in report.spending_by_category()

    def test_income_is_ignored(self, report, ledger):
        assert sum(report.spending_by_category().values()) == ledger.total_expenses

    def test_empty_ledger(self):
        assert ReportGenerator(TransactionLedger()).spending_by_category() == {}


class TestIncomeBySource:

    def test_totals_per_source(self, report):
        totals = report.income_by_source()
        assert totals[IncomeSource.SALARY] == Decimal("4800.00")
        assert totals[IncomeSource.REFUND] == Decimal("30.00")

    def test_expenses_are_ignored(self, report, ledger):
        assert sum(report.income_by_source().values()) == ledger.total_income


class TestMonthlyBreakdown:

    def test_one_row_per_month_oldest_first(self, report):
        labels = [m.label for m in report.monthly_breakdown()]
        assert labels == ["2026-08", "2026-09"]

    def test_august_numbers(self, report):
        august = report.monthly_breakdown()[0]
        assert august.income == Decimal("2400.00")
        assert august.expenses == Decimal("890.00")
        assert august.net == Decimal("1510.00")

    def test_net_can_be_negative(self):
        ledger = TransactionLedger([Expense("10", "Gum", "other", "2026-01-05")])
        assert ReportGenerator(ledger).monthly_breakdown()[0].net == Decimal("-10.00")

    def test_months_add_up_to_the_balance(self, report, ledger):
        assert sum(m.net for m in report.monthly_breakdown()) == ledger.balance

    def test_same_month_different_years_kept_apart(self):
        ledger = TransactionLedger([
            Expense("1", "a", "other", "2025-09-01"),
            Expense("1", "b", "other", "2026-09-01"),
        ])
        assert len(ReportGenerator(ledger).monthly_breakdown()) == 2

    def test_label_pads_month(self):
        assert MonthSummary(2026, 3, Decimal("0"), Decimal("0")).label == "2026-03"


class TestRecurringIncome:

    def test_only_recurring_counts(self, report):
        assert report.recurring_income() == Decimal("4800.00")

    def test_none_recurring(self):
        ledger = TransactionLedger([Income("5", "Gift", "gift", "2026-09-01")])
        assert ReportGenerator(ledger).recurring_income() == Decimal("0.00")


class TestBudget:

    def test_limits_from_text(self):
        budget = Budget({"groceries": "250", "eating out": 60})
        assert budget.limit_for(Category.GROCERIES) == Decimal("250.00")
        assert budget.limit_for("eating_out") == Decimal("60.00")

    def test_missing_limit_is_none(self):
        assert Budget().limit_for(Category.BILLS) is None

    def test_set_and_remove(self):
        budget = Budget()
        budget.set_limit(Category.TRANSPORT, "45")
        assert len(budget) == 1
        budget.remove_limit("transport")
        assert len(budget) == 0

    def test_setting_again_replaces(self):
        budget = Budget({"bills": 100})
        budget.set_limit("bills", 120)
        assert budget.limit_for("bills") == Decimal("120.00")

    @pytest.mark.parametrize("bad", ["0", "-5", "lots", 1.5, True, "NaN"])
    def test_bad_limits_are_rejected(self, bad):
        with pytest.raises(ValidationError):
            Budget({"groceries": bad})

    def test_unknown_category_is_rejected(self):
        with pytest.raises(ValidationError):
            Budget({"yachts": 100})


class TestCheckBudget:

    def test_only_that_month_counts(self, report):
        statuses = report.check_budget(Budget({"groceries": 100}), 2026, 9)
        assert statuses[0].spent == Decimal("82.35")

    def test_over_budget(self, report):
        status = report.check_budget(Budget({"eating out": 50}), 2026, 9)[0]
        assert status.is_over
        assert status.remaining == Decimal("-25.50")
        assert status.percent_used == Decimal("151.0")

    def test_under_budget(self, report):
        status = report.check_budget(Budget({"groceries": 100}), 2026, 9)[0]
        assert not status.is_over
        assert status.remaining == Decimal("17.65")

    def test_category_with_no_spending(self, report):
        status = report.check_budget(Budget({"health": 30}), 2026, 9)[0]
        assert status.spent == Decimal("0.00")
        assert status.percent_used == Decimal("0.0")

    def test_worst_first(self, report):
        budget = Budget({"groceries": 1000, "eating out": 50, "housing": 900})
        order = [s.category for s in report.check_budget(budget, 2026, 9)]
        assert order == [Category.EATING_OUT, Category.HOUSING, Category.GROCERIES]

    def test_exactly_on_limit_is_not_over(self):
        assert not BudgetStatus(Category.BILLS, Decimal("10"), Decimal("10")).is_over


class TestFormatter:

    def test_category_table(self, report):
        text = ReportFormatter().category_table(report.spending_by_category())
        assert "Housing" in text and "Total" in text and "1,922.85" in text

    def test_monthly_table_shows_sign(self):
        months = [MonthSummary(2026, 9, Decimal("10"), Decimal("25"))]
        assert "-£15.00" in ReportFormatter().monthly_table(months)

    def test_budget_table_flags_overspend(self, report):
        statuses = report.check_budget(Budget({"eating out": 50}), 2026, 9)
        assert "OVER" in ReportFormatter().budget_table(statuses)

    def test_source_table(self, report):
        assert "Salary" in ReportFormatter().source_table(report.income_by_source())

    @pytest.mark.parametrize("method", [
        "category_table", "source_table", "monthly_table", "budget_table",
    ])
    def test_empty_input_gives_a_message(self, method):
        empty = {} if method in ("category_table", "source_table") else []
        assert getattr(ReportFormatter(), method)(empty).startswith("No ")


def test_reports_do_not_change_the_ledger(report, ledger):
    before = list(ledger)
    report.spending_by_category()
    report.monthly_breakdown()
    report.check_budget(Budget({"groceries": 1}), 2026, 9)
    assert list(ledger) == before
