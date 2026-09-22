"""Unit tests for ``TransactionLedger``.

The suite is written around three questions:

1. Does the ledger protect its invariants (unique ids, transactions only)?
2. Does it behave like a real Python container, so that ``len``, ``in``,
   indexing, slicing, iteration and sorting all work as a reader expects?
3. Are the aggregates correct for a mixed collection, in pence, using
   ``Decimal``?

Shared setup lives in ``pytest`` fixtures rather than in ``setUp`` style
methods, so each test states exactly what it needs.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from expense_tracker import (
    Category,
    DuplicateTransactionError,
    Expense,
    Income,
    IncomeSource,
    LedgerError,
    TransactionLedger,
    TransactionNotFoundError,
    ValidationError,
)


@pytest.fixture
def salary() -> Income:
    """A single recurring income."""
    return Income("2400.00", "Salary", IncomeSource.SALARY, "2026-09-01",
                  is_recurring=True)


@pytest.fixture
def rent() -> Expense:
    """A single large expense."""
    return Expense("875.00", "Rent", Category.HOUSING, "2026-09-02")


@pytest.fixture
def coffee() -> Expense:
    """A single small expense."""
    return Expense("3.40", "Flat white", Category.EATING_OUT, "2026-09-08")


@pytest.fixture
def ledger(salary: Income, rent: Expense, coffee: Expense) -> TransactionLedger:
    """A ledger holding one income and two expenses, in that order."""
    return TransactionLedger([salary, rent, coffee])


class TestConstruction:
    """Creating ledgers, empty or pre-filled."""

    def test_new_ledger_is_empty(self) -> None:
        assert len(TransactionLedger()) == 0

    def test_empty_ledger_is_falsey(self) -> None:
        assert not TransactionLedger()

    def test_populated_ledger_is_truthy(self, ledger: TransactionLedger) -> None:
        assert ledger

    def test_accepts_any_iterable(self, salary: Income, rent: Expense) -> None:
        # A generator, not a list, to prove nothing assumes a sequence.
        assert len(TransactionLedger(t for t in (salary, rent))) == 2

    def test_preserves_insertion_order_not_date_order(
        self, coffee: Expense, salary: Income
    ) -> None:
        later_date_first = TransactionLedger([coffee, salary])
        assert later_date_first[0] is coffee


class TestInvariants:
    """The ledger refuses anything that would corrupt it."""

    def test_rejects_a_duplicate_transaction(
        self, ledger: TransactionLedger, salary: Income
    ) -> None:
        with pytest.raises(DuplicateTransactionError):
            ledger.add(salary)

    def test_ledger_is_unchanged_after_a_rejected_duplicate(
        self, ledger: TransactionLedger, salary: Income
    ) -> None:
        with pytest.raises(DuplicateTransactionError):
            ledger.add(salary)
        assert len(ledger) == 3

    @pytest.mark.parametrize("not_a_transaction", ["3.40", 42, None, ["rent"]])
    def test_rejects_non_transactions(self, not_a_transaction: object) -> None:
        with pytest.raises(ValidationError):
            TransactionLedger().add(not_a_transaction)  # type: ignore[arg-type]

    def test_two_equal_looking_transactions_both_fit(self) -> None:
        # Same price, same day, same words: still two separate coffees,
        # because identity is by UUID.
        first = Expense("3.40", "Flat white", Category.EATING_OUT, "2026-09-08")
        second = Expense("3.40", "Flat white", Category.EATING_OUT, "2026-09-08")
        assert len(TransactionLedger([first, second])) == 2

    def test_ledger_errors_share_one_base_class(
        self, ledger: TransactionLedger, salary: Income
    ) -> None:
        # A caller can catch every collection level problem with one name.
        with pytest.raises(LedgerError):
            ledger.add(salary)
        with pytest.raises(LedgerError):
            ledger.remove("missing")


class TestRemovalAndLookup:
    """Finding and deleting by identifier."""

    def test_get_returns_the_transaction(
        self, ledger: TransactionLedger, rent: Expense
    ) -> None:
        assert ledger.get(rent.transaction_id) is rent

    def test_get_raises_for_an_unknown_id(self, ledger: TransactionLedger) -> None:
        with pytest.raises(TransactionNotFoundError):
            ledger.get("not-a-real-id")

    def test_remove_returns_and_deletes(
        self, ledger: TransactionLedger, rent: Expense
    ) -> None:
        assert ledger.remove(rent.transaction_id) is rent
        assert len(ledger) == 2
        assert rent not in ledger

    def test_remove_raises_for_an_unknown_id(self, ledger: TransactionLedger) -> None:
        with pytest.raises(TransactionNotFoundError):
            ledger.remove("not-a-real-id")

    def test_removed_id_can_be_reused_by_a_new_transaction(
        self, ledger: TransactionLedger, rent: Expense
    ) -> None:
        # Proves the index is cleaned up on removal, not just the list.
        ledger.remove(rent.transaction_id)
        replacement = Expense("900", "Rent", Category.HOUSING,
                              transaction_id=rent.transaction_id)
        ledger.add(replacement)
        assert ledger.get(rent.transaction_id) is replacement

    def test_clear_empties_the_ledger(self, ledger: TransactionLedger) -> None:
        ledger.clear()
        assert len(ledger) == 0
        assert ledger.balance == Decimal("0.00")


class TestContainerProtocol:
    """The ledger behaves like any other Python sequence."""

    def test_len(self, ledger: TransactionLedger) -> None:
        assert len(ledger) == 3

    def test_index_access(self, ledger: TransactionLedger, salary: Income) -> None:
        assert ledger[0] is salary

    def test_negative_index_access(
        self, ledger: TransactionLedger, coffee: Expense
    ) -> None:
        assert ledger[-1] is coffee

    def test_index_out_of_range_raises_index_error(
        self, ledger: TransactionLedger
    ) -> None:
        with pytest.raises(IndexError):
            ledger[99]

    def test_slicing_returns_another_ledger(self, ledger: TransactionLedger) -> None:
        window = ledger[:2]
        assert isinstance(window, TransactionLedger)
        assert len(window) == 2

    def test_slice_is_independent_of_the_original(
        self, ledger: TransactionLedger, coffee: Expense
    ) -> None:
        window = ledger[:2]
        window.remove(window[0].transaction_id)
        assert len(ledger) == 3

    def test_iteration_yields_every_transaction(
        self, ledger: TransactionLedger
    ) -> None:
        assert len(list(ledger)) == 3

    def test_membership_by_object(
        self, ledger: TransactionLedger, rent: Expense
    ) -> None:
        assert rent in ledger

    def test_membership_by_id_string(
        self, ledger: TransactionLedger, rent: Expense
    ) -> None:
        assert rent.transaction_id in ledger

    def test_membership_is_false_for_unrelated_types(
        self, ledger: TransactionLedger
    ) -> None:
        assert 42 not in ledger

    def test_sorting_uses_transaction_dates(self, ledger: TransactionLedger) -> None:
        dates = [t.transaction_date for t in sorted(ledger)]
        assert dates == sorted(dates)

    def test_reversed_works_via_the_sequence_base(
        self, ledger: TransactionLedger, coffee: Expense
    ) -> None:
        assert next(reversed(ledger)) is coffee

    def test_index_and_count_come_free_from_sequence(
        self, ledger: TransactionLedger, rent: Expense
    ) -> None:
        assert ledger.index(rent) == 1
        assert ledger.count(rent) == 1

    def test_unpacking_works(self, ledger: TransactionLedger) -> None:
        first, *rest = ledger
        assert first is ledger[0]
        assert len(rest) == 2

    def test_adding_two_ledgers_makes_a_third(
        self, salary: Income, rent: Expense
    ) -> None:
        combined = TransactionLedger([salary]) + TransactionLedger([rent])
        assert len(combined) == 2

    def test_adding_leaves_both_operands_unchanged(
        self, salary: Income, rent: Expense
    ) -> None:
        left, right = TransactionLedger([salary]), TransactionLedger([rent])
        left + right
        assert len(left) == 1 and len(right) == 1

    def test_adding_overlapping_ledgers_raises(self, salary: Income) -> None:
        with pytest.raises(DuplicateTransactionError):
            TransactionLedger([salary]) + TransactionLedger([salary])

    def test_adding_an_unrelated_type_raises_type_error(
        self, ledger: TransactionLedger
    ) -> None:
        with pytest.raises(TypeError):
            ledger + 5  # type: ignore[operator]


class TestAggregates:
    """Totals over a mixed collection, computed without type checks."""

    def test_balance(self, ledger: TransactionLedger) -> None:
        # 2400.00 in, 878.40 out
        assert ledger.balance == Decimal("1521.60")

    def test_total_income(self, ledger: TransactionLedger) -> None:
        assert ledger.total_income == Decimal("2400.00")

    def test_total_expenses_is_positive(self, ledger: TransactionLedger) -> None:
        assert ledger.total_expenses == Decimal("878.40")

    def test_empty_ledger_totals_are_decimal_zero(self) -> None:
        empty = TransactionLedger()
        assert empty.balance == Decimal("0.00")
        assert isinstance(empty.total_income, Decimal)

    def test_totals_use_exact_decimal_arithmetic(self) -> None:
        # The classic float failure: 0.1 + 0.2 != 0.3 in binary floating
        # point. Summing these as Decimal gives exactly 0.30.
        ledger = TransactionLedger(
            [Income("0.10", "A"), Income("0.20", "B")]
        )
        assert ledger.total_income == Decimal("0.30")

    def test_counts_by_transaction_type_tag(self, ledger: TransactionLedger) -> None:
        assert ledger.of_type_count("income") == 1
        assert ledger.of_type_count("expense") == 2

    def test_summary_mentions_the_balance(self, ledger: TransactionLedger) -> None:
        assert "1,521.60" in ledger.summary()

    def test_summary_of_an_empty_ledger_is_readable(self) -> None:
        assert TransactionLedger().summary() == "Ledger is empty."


class TestFiltering:
    """Filters return new ledgers and leave the original alone."""

    def test_filter_by_predicate(self, ledger: TransactionLedger) -> None:
        big = ledger.filter_by(lambda t: t.amount > Decimal("100"))
        assert len(big) == 2

    def test_filter_returns_a_ledger_not_a_list(
        self, ledger: TransactionLedger
    ) -> None:
        assert isinstance(ledger.filter_by(lambda t: True), TransactionLedger)

    def test_filter_does_not_mutate_the_original(
        self, ledger: TransactionLedger
    ) -> None:
        ledger.filter_by(lambda t: False)
        assert len(ledger) == 3

    def test_filters_can_be_chained(self, ledger: TransactionLedger) -> None:
        result = (
            ledger.of_type(Expense)
            .filter_by(lambda t: t.amount < Decimal("100"))
        )
        assert len(result) == 1

    def test_of_type_selects_one_subclass(self, ledger: TransactionLedger) -> None:
        assert len(ledger.of_type(Income)) == 1
        assert len(ledger.of_type(Expense)) == 2

    def test_filtered_ledger_recomputes_its_own_totals(
        self, ledger: TransactionLedger
    ) -> None:
        assert ledger.of_type(Expense).total_expenses == Decimal("878.40")


class TestSerialization:
    """Preparing the ledger for the Day 3 storage layer."""

    def test_to_dicts_returns_one_record_per_transaction(
        self, ledger: TransactionLedger
    ) -> None:
        assert len(ledger.to_dicts()) == 3

    def test_records_carry_their_type_tag(self, ledger: TransactionLedger) -> None:
        tags = {record["type"] for record in ledger.to_dicts()}
        assert tags == {"income", "expense"}

    def test_records_are_json_serialisable(self, ledger: TransactionLedger) -> None:
        import json

        assert json.loads(json.dumps(ledger.to_dicts()))


class TestStringRepresentations:
    """``repr`` for debugging, ``str`` for people."""

    def test_repr_reports_size_and_balance(self, ledger: TransactionLedger) -> None:
        text = repr(ledger)
        assert "size=3" in text
        assert "1521.60" in text

    def test_str_prints_one_line_per_transaction(
        self, ledger: TransactionLedger
    ) -> None:
        assert len(str(ledger).splitlines()) == 3

    def test_str_of_an_empty_ledger_is_readable(self) -> None:
        assert str(TransactionLedger()) == "Ledger is empty."
