"""Tests for the Income transaction type.

Only the public interface is touched. Nothing here reads an attribute
starting with an underscore, so the internals can be reworked on Day 6
without rewriting the suite.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from expense_tracker import (
    Expense,
    Income,
    IncomeSource,
    SerializationError,
    Transaction,
    ValidationError,
)


class TestConstruction:
    """Building an income and reading its fields back."""

    def test_stores_amount_as_decimal(self):
        income = Income("2400", "Salary")
        assert income.amount == Decimal("2400.00")
        assert isinstance(income.amount, Decimal)

    def test_rounds_half_up_to_two_places(self):
        assert Income("0.125", "Interest").amount == Decimal("0.13")

    def test_defaults_are_sensible(self):
        income = Income("50", "Birthday money")
        assert income.source is IncomeSource.OTHER
        assert income.is_recurring is False
        assert income.transaction_date == date.today()

    def test_accepts_source_as_text(self):
        assert Income("10", "Cashback", "  Refund ").source is IncomeSource.REFUND

    def test_accepts_iso_date_text(self):
        income = Income("10", "Cashback", transaction_date="2026-09-20")
        assert income.transaction_date == date(2026, 9, 20)

    def test_generates_a_unique_id_per_instance(self):
        first, second = Income("10", "One"), Income("10", "One")
        assert first.transaction_id != second.transaction_id

    def test_keeps_an_id_it_is_given(self):
        income = Income("10", "One", transaction_id="fixed-id")
        assert income.transaction_id == "fixed-id"


class TestValidation:
    """Bad input is refused, at construction and afterwards."""

    @pytest.mark.parametrize("bad_amount", ["0", "-1", "abc", None, "NaN"])
    def test_rejects_invalid_amounts(self, bad_amount):
        with pytest.raises(ValidationError):
            Income(bad_amount, "Salary")

    @pytest.mark.parametrize("bad_description", ["", "   ", 42, None])
    def test_rejects_invalid_descriptions(self, bad_description):
        with pytest.raises(ValidationError):
            Income("10", bad_description)

    def test_rejects_unknown_source(self):
        with pytest.raises(ValidationError, match="Unknown incomesource"):
            Income("10", "Mystery", "lottery")

    @pytest.mark.parametrize("bad_flag", ["yes", 1, 0, None])
    def test_rejects_non_boolean_recurring_flag(self, bad_flag):
        # 1 and 0 are truthy and falsey but are not booleans. Letting them
        # through would store the wrong thing without complaining.
        with pytest.raises(ValidationError):
            Income("10", "Salary", is_recurring=bad_flag)

    def test_rejects_invalid_assignment_after_construction(self):
        income = Income("10", "Salary")
        with pytest.raises(ValidationError):
            income.amount = "-5"

    def test_object_is_unchanged_after_a_rejected_assignment(self):
        income = Income("10", "Salary")
        with pytest.raises(ValidationError):
            income.source = 99
        assert income.source is IncomeSource.OTHER
        assert income.amount == Decimal("10.00")


class TestPolymorphism:
    """Income and Expense answer the same questions differently."""

    def test_is_a_transaction(self):
        assert isinstance(Income("10", "Salary"), Transaction)

    def test_signed_amount_is_positive(self):
        assert Income("2400", "Salary").signed_amount == Decimal("2400.00")

    def test_signed_amount_is_opposite_to_an_expense(self):
        income = Income("100", "Refund")
        expense = Expense("100", "Purchase")
        assert income.signed_amount == -expense.signed_amount

    def test_mixed_total_needs_no_type_checks(self):
        transactions: list[Transaction] = [
            Income("2400", "Salary"),
            Expense("875", "Rent"),
            Expense("62.35", "Groceries"),
        ]
        total = sum(t.signed_amount for t in transactions)
        assert total == Decimal("1462.65")

    def test_summary_line_marks_the_direction(self):
        assert "+£" in Income("2400", "Salary").summary_line()
        assert "-£" in Expense("875", "Rent").summary_line()

    def test_summary_line_flags_recurring_income(self):
        line = Income("2400", "Salary", is_recurring=True).summary_line()
        assert "(recurring)" in line

    def test_str_uses_the_summary_line(self):
        income = Income("2400", "Salary")
        assert str(income) == income.summary_line()

    def test_transaction_type_tag_is_overridden(self):
        assert Income("10", "Salary").TRANSACTION_TYPE == "income"


class TestEquality:
    """Identity comes from the id, not the values."""

    def test_two_identical_incomes_are_not_equal(self):
        assert Income("10", "Salary") != Income("10", "Salary")

    def test_an_income_equals_itself(self):
        income = Income("10", "Salary")
        assert income == income

    def test_an_income_never_equals_an_expense_with_the_same_id(self):
        # Type is part of identity. A refund and a purchase sharing a row id
        # would be a data error, not two views of one thing.
        income = Income("10", "Thing", transaction_id="shared")
        expense = Expense("10", "Thing", transaction_id="shared")
        assert income != expense

    def test_is_hashable_and_usable_in_a_set(self):
        income = Income("10", "Salary")
        assert {income, income} == {income}

    def test_sorts_by_date(self):
        earlier = Income("10", "A", transaction_date="2026-01-01")
        later = Income("10", "B", transaction_date="2026-06-01")
        assert sorted([later, earlier]) == [earlier, later]


class TestSerialization:
    """A round trip must not lose or change anything."""

    def test_to_dict_contains_the_income_fields(self):
        data = Income("2400", "Salary", IncomeSource.SALARY, "2026-09-01",
                      is_recurring=True).to_dict()
        assert data["type"] == "income"
        assert data["source"] == "salary"
        assert data["is_recurring"] is True
        assert data["amount"] == "2400.00"
        assert data["date"] == "2026-09-01"

    def test_round_trip_preserves_every_field(self):
        original = Income("2400", "Salary", IncomeSource.SALARY, "2026-09-01",
                          is_recurring=True)
        restored = Income.from_dict(original.to_dict())

        assert restored == original  # same id, so the same entity
        assert restored.amount == original.amount
        assert restored.description == original.description
        assert restored.source is original.source
        assert restored.is_recurring == original.is_recurring
        assert restored.transaction_date == original.transaction_date

    def test_round_trip_survives_json(self):
        import json

        original = Income("180.50", "Tutoring", IncomeSource.FREELANCE)
        restored = Income.from_dict(json.loads(json.dumps(original.to_dict())))
        assert restored.amount == Decimal("180.50")
        assert restored.source is IncomeSource.FREELANCE

    @pytest.mark.parametrize("missing_key", ["amount", "description"])
    def test_missing_required_key_raises(self, missing_key):
        data = Income("10", "Salary").to_dict()
        del data[missing_key]
        with pytest.raises(SerializationError, match=missing_key):
            Income.from_dict(data)

    def test_missing_optional_keys_fall_back_to_defaults(self):
        # An older record, saved before these fields existed, still loads
        # rather than breaking the whole file.
        restored = Income.from_dict({"amount": "10", "description": "Salary"})
        assert restored.source is IncomeSource.OTHER
        assert restored.is_recurring is False
