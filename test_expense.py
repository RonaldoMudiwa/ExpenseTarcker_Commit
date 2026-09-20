"""Unit tests for the day 1 domain model.

Run them from the project root with::

    pytest -v

Tests are grouped into classes by the behaviour under test rather than one
flat file of functions. Each test name states the expected behaviour, so a
failing run reads like a list of broken requirements.

The tests exercise the public interface only (constructors, properties,
``to_dict``). Private helpers such as ``_validate_amount`` are covered
indirectly, which keeps the tests from breaking every time the internals are
refactored.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from expense_tracker import (
    Category,
    Expense,
    PaymentMethod,
    SerializationError,
    Transaction,
    ValidationError,
)


class TestConstruction:
    """Creating an expense from well formed input."""

    def test_stores_amount_as_decimal_with_two_places(self):
        expense = Expense("3.4", "Flat white", Category.EATING_OUT)
        assert expense.amount == Decimal("3.40")
        assert isinstance(expense.amount, Decimal)

    def test_accepts_int_float_and_string_amounts(self):
        assert Expense(28, "Travel", Category.TRANSPORT).amount == Decimal("28.00")
        assert Expense(9.99, "Netflix", Category.ENTERTAINMENT).amount == Decimal("9.99")
        assert Expense("12.50", "Books", Category.EDUCATION).amount == Decimal("12.50")

    def test_rounds_half_up_the_way_people_expect(self):
        assert Expense("0.125", "Rounding", Category.OTHER).amount == Decimal("0.13")

    def test_collapses_whitespace_in_description(self):
        expense = Expense("5.00", "  Weekly   shop  ", Category.GROCERIES)
        assert expense.description == "Weekly shop"

    def test_defaults_date_to_today(self):
        assert Expense("5.00", "Lunch", Category.EATING_OUT).transaction_date == date.today()

    def test_parses_iso_date_string(self):
        expense = Expense("5.00", "Lunch", Category.EATING_OUT, "2026-09-18")
        assert expense.transaction_date == date(2026, 9, 18)

    def test_strips_time_from_datetime(self):
        expense = Expense("5.00", "Lunch", Category.EATING_OUT, datetime(2026, 9, 18, 14, 30))
        assert expense.transaction_date == date(2026, 9, 18)

    def test_generates_a_unique_id_per_expense(self):
        first = Expense("5.00", "Lunch", Category.EATING_OUT)
        second = Expense("5.00", "Lunch", Category.EATING_OUT)
        assert first.transaction_id != second.transaction_id

    def test_accepts_category_and_payment_method_as_text(self):
        expense = Expense("5.00", "Lunch", "Eating Out", payment_method="credit-card")
        assert expense.category is Category.EATING_OUT
        assert expense.payment_method is PaymentMethod.CREDIT_CARD


class TestValidation:
    """The object must refuse to exist in an invalid state."""

    @pytest.mark.parametrize("bad_amount", [0, -1, "-4.50", Decimal("0.00")])
    def test_rejects_non_positive_amounts(self, bad_amount):
        with pytest.raises(ValidationError):
            Expense(bad_amount, "Bad", Category.OTHER)

    @pytest.mark.parametrize("bad_amount", ["abc", None, True, [5]])
    def test_rejects_amounts_that_are_not_numbers(self, bad_amount):
        with pytest.raises(ValidationError):
            Expense(bad_amount, "Bad", Category.OTHER)

    @pytest.mark.parametrize("bad_description", ["", "   ", 42, None])
    def test_rejects_empty_or_non_text_descriptions(self, bad_description):
        with pytest.raises(ValidationError):
            Expense("5.00", bad_description, Category.OTHER)

    def test_rejects_over_long_descriptions(self):
        with pytest.raises(ValidationError):
            Expense("5.00", "x" * 121, Category.OTHER)

    def test_rejects_unknown_category(self):
        with pytest.raises(ValidationError):
            Expense("5.00", "Lunch", "space travel")

    def test_rejects_malformed_date(self):
        with pytest.raises(ValidationError):
            Expense("5.00", "Lunch", Category.OTHER, "18/09/2026")

    def test_setter_validation_leaves_the_object_untouched(self):
        expense = Expense("5.00", "Lunch", Category.EATING_OUT)
        with pytest.raises(ValidationError):
            expense.amount = -10
        assert expense.amount == Decimal("5.00")

    def test_transaction_id_is_read_only(self):
        expense = Expense("5.00", "Lunch", Category.EATING_OUT)
        with pytest.raises(AttributeError):
            expense.transaction_id = "tampered"


class TestAbstraction:
    """The base class describes a contract and cannot stand alone."""

    def test_transaction_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            Transaction("5.00", "Nope")  # type: ignore[abstract]

    def test_expense_is_a_transaction(self):
        assert isinstance(Expense("5.00", "Lunch", Category.OTHER), Transaction)


class TestPolymorphism:
    """Behaviour that varies by subclass while the interface stays fixed."""

    def test_signed_amount_is_negative_for_expenses(self):
        expense = Expense("42.15", "Weekly shop", Category.GROCERIES)
        assert expense.signed_amount == Decimal("-42.15")
        assert expense.amount == Decimal("42.15")

    def test_totals_can_be_summed_through_the_base_interface(self):
        items: list[Transaction] = [
            Expense("10.00", "One", Category.OTHER),
            Expense("5.50", "Two", Category.OTHER),
        ]
        total = sum((item.signed_amount for item in items), start=Decimal("0.00"))
        assert total == Decimal("-15.50")

    def test_str_uses_the_subclass_summary_line(self):
        expense = Expense("3.40", "Flat white", Category.EATING_OUT, "2026-09-18")
        rendered = str(expense)
        assert "2026-09-18" in rendered
        assert "3.40" in rendered
        assert "Flat white" in rendered


class TestEqualityAndOrdering:
    """Entity semantics: identity comes from the stored identifier."""

    def test_two_expenses_with_identical_data_are_not_equal(self):
        first = Expense("5.00", "Lunch", Category.EATING_OUT, "2026-09-18")
        second = Expense("5.00", "Lunch", Category.EATING_OUT, "2026-09-18")
        assert first != second

    def test_same_id_means_equal(self):
        first = Expense("5.00", "Lunch", Category.EATING_OUT)
        second = Expense.from_dict(first.to_dict())
        assert first == second
        assert hash(first) == hash(second)

    def test_expenses_can_live_in_a_set(self):
        expense = Expense("5.00", "Lunch", Category.EATING_OUT)
        assert len({expense, expense}) == 1

    def test_comparison_with_other_types_is_not_an_error(self):
        assert Expense("5.00", "Lunch", Category.OTHER) != "not a transaction"

    def test_sorting_is_by_date(self):
        later = Expense("5.00", "Later", Category.OTHER, "2026-09-18")
        earlier = Expense("5.00", "Earlier", Category.OTHER, "2026-09-01")
        assert sorted([later, earlier])[0] is earlier


class TestSerialization:
    """Converting to and from plain dictionaries."""

    def test_to_dict_contains_every_field(self):
        expense = Expense("3.40", "Flat white", Category.EATING_OUT, "2026-09-18",
                          PaymentMethod.CASH)
        data = expense.to_dict()
        assert data == {
            "transaction_id": expense.transaction_id,
            "type": "expense",
            "amount": "3.40",
            "description": "Flat white",
            "date": "2026-09-18",
            "category": "eating_out",
            "payment_method": "cash",
        }

    def test_round_trip_preserves_every_field(self):
        original = Expense("42.15", "Weekly shop", Category.GROCERIES, "2026-09-14",
                           PaymentMethod.DEBIT_CARD)
        restored = Expense.from_dict(original.to_dict())
        assert restored.amount == original.amount
        assert restored.description == original.description
        assert restored.category is original.category
        assert restored.payment_method is original.payment_method
        assert restored.transaction_date == original.transaction_date
        assert restored.transaction_id == original.transaction_id

    def test_missing_required_key_raises_serialization_error(self):
        with pytest.raises(SerializationError):
            Expense.from_dict({"description": "No amount"})


class TestEnums:
    """The enum helpers shared by category and payment method."""

    def test_from_string_is_case_and_separator_insensitive(self):
        assert Category.from_string("  Eating Out ") is Category.EATING_OUT
        assert PaymentMethod.from_string("bank-transfer") is PaymentMethod.BANK_TRANSFER

    def test_label_is_human_readable(self):
        assert Category.EATING_OUT.label == "Eating Out"

    def test_unknown_value_lists_the_allowed_options(self):
        with pytest.raises(ValidationError) as caught:
            Category.from_string("space travel")
        assert "groceries" in str(caught.value)
