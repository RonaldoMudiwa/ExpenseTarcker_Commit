"""Tests for the filters. One small ledger is used throughout."""

from __future__ import annotations

from datetime import date

import pytest

from expense_tracker import (
    AmountRangeFilter,
    Category,
    CategoryFilter,
    DateRangeFilter,
    Expense,
    Income,
    IncomeSource,
    IncomeSourceFilter,
    MatchAll,
    TextSearchFilter,
    TransactionFilter,
    TransactionLedger,
    TypeFilter,
    ValidationError,
    all_of,
)


@pytest.fixture
def ledger() -> TransactionLedger:
    return TransactionLedger(
        [
            Income("2400.00", "September salary", IncomeSource.SALARY, "2026-09-01"),
            Expense("875.00", "Rent", Category.HOUSING, "2026-09-02"),
            Expense("62.35", "Weekly shop at TESCO", Category.GROCERIES, "2026-09-03"),
            Expense("3.40", "Flat white", Category.EATING_OUT, "2026-09-08"),
            Income("24.99", "Returned headphones", IncomeSource.REFUND, "2026-09-30"),
            Expense("18.00", "Tesco meal deal x5", Category.EATING_OUT, "2026-10-01"),
        ]
    )


def names(ledger: TransactionLedger) -> list[str]:
    """Just the descriptions, so failures are easy to read."""
    return [t.description for t in ledger]


class TestDateRange:

    def test_both_ends_are_included(self, ledger):
        result = ledger.filter_by(DateRangeFilter("2026-09-02", "2026-09-03"))
        assert names(result) == ["Rent", "Weekly shop at TESCO"]

    def test_start_only(self, ledger):
        result = ledger.filter_by(DateRangeFilter(start="2026-09-30"))
        assert names(result) == ["Returned headphones", "Tesco meal deal x5"]

    def test_end_only(self, ledger):
        result = ledger.filter_by(DateRangeFilter(end="2026-09-01"))
        assert names(result) == ["September salary"]

    def test_no_ends_matches_everything(self, ledger):
        assert len(ledger.filter_by(DateRangeFilter())) == len(ledger)

    def test_accepts_date_objects(self, ledger):
        result = ledger.filter_by(DateRangeFilter(date(2026, 10, 1), date(2026, 10, 31)))
        assert names(result) == ["Tesco meal deal x5"]

    def test_start_after_end_is_rejected(self):
        with pytest.raises(ValidationError, match="after"):
            DateRangeFilter("2026-09-30", "2026-09-01")

    def test_bad_date_text_is_rejected(self):
        with pytest.raises(ValidationError):
            DateRangeFilter("30/09/2026")

    def test_wrong_type_is_rejected(self):
        with pytest.raises(ValidationError):
            DateRangeFilter(20260901)

    def test_for_month_covers_first_and_last_day(self, ledger):
        result = ledger.filter_by(DateRangeFilter.for_month(2026, 9))
        assert "September salary" in names(result)
        assert "Returned headphones" in names(result)
        assert "Tesco meal deal x5" not in names(result)

    @pytest.mark.parametrize("year, month, last_day", [
        (2026, 2, 28),
        (2028, 2, 29),   # leap year
        (2026, 4, 30),
        (2026, 12, 31),
    ])
    def test_for_month_knows_month_lengths(self, year, month, last_day):
        assert DateRangeFilter.for_month(year, month).end.day == last_day

    @pytest.mark.parametrize("month", [0, 13])
    def test_for_month_rejects_bad_month(self, month):
        with pytest.raises(ValidationError):
            DateRangeFilter.for_month(2026, month)


class TestCategory:

    def test_one_category(self, ledger):
        assert names(ledger.filter_by(CategoryFilter(Category.HOUSING))) == ["Rent"]

    def test_several_categories(self, ledger):
        result = ledger.filter_by(CategoryFilter(Category.GROCERIES, Category.EATING_OUT))
        assert len(result) == 3

    def test_accepts_text(self, ledger):
        assert len(ledger.filter_by(CategoryFilter("eating out"))) == 2

    def test_income_never_matches(self, ledger):
        every_category = CategoryFilter(*Category)
        assert all(isinstance(t, Expense) for t in ledger.filter_by(every_category))

    def test_needs_at_least_one(self):
        with pytest.raises(ValidationError):
            CategoryFilter()

    def test_unknown_category_is_rejected(self):
        with pytest.raises(ValidationError):
            CategoryFilter("holidays on the moon")


class TestIncomeSource:

    def test_one_source(self, ledger):
        result = ledger.filter_by(IncomeSourceFilter(IncomeSource.REFUND))
        assert names(result) == ["Returned headphones"]

    def test_expenses_never_match(self, ledger):
        result = ledger.filter_by(IncomeSourceFilter(*IncomeSource))
        assert all(isinstance(t, Income) for t in result)

    def test_needs_at_least_one(self):
        with pytest.raises(ValidationError):
            IncomeSourceFilter()


class TestType:

    def test_expenses_only(self, ledger):
        assert len(ledger.filter_by(TypeFilter(Expense))) == 4

    def test_income_only(self, ledger):
        assert len(ledger.filter_by(TypeFilter(Income))) == 2

    def test_rejects_non_transaction_class(self):
        with pytest.raises(ValidationError):
            TypeFilter(str)


class TestAmountRange:

    def test_minimum_is_included(self, ledger):
        result = ledger.filter_by(AmountRangeFilter(minimum="875.00"))
        assert names(result) == ["September salary", "Rent"]

    def test_maximum_is_included(self, ledger):
        result = ledger.filter_by(AmountRangeFilter(maximum="18"))
        assert names(result) == ["Flat white", "Tesco meal deal x5"]

    def test_between(self, ledger):
        result = ledger.filter_by(AmountRangeFilter(20, 100))
        assert names(result) == ["Weekly shop at TESCO", "Returned headphones"]

    def test_min_above_max_is_rejected(self):
        with pytest.raises(ValidationError):
            AmountRangeFilter(100, 10)

    def test_float_is_rejected(self):
        with pytest.raises(ValidationError):
            AmountRangeFilter(minimum=0.1)

    def test_bool_is_rejected(self):
        with pytest.raises(ValidationError):
            AmountRangeFilter(minimum=True)

    def test_text_that_is_not_a_number_is_rejected(self):
        with pytest.raises(ValidationError):
            AmountRangeFilter(minimum="lots")


class TestTextSearch:

    def test_ignores_case(self, ledger):
        result = ledger.filter_by(TextSearchFilter("tesco"))
        assert names(result) == ["Weekly shop at TESCO", "Tesco meal deal x5"]

    def test_matches_part_of_a_word(self, ledger):
        assert names(ledger.filter_by(TextSearchFilter("head"))) == ["Returned headphones"]

    def test_trims_spaces(self, ledger):
        assert len(ledger.filter_by(TextSearchFilter("  rent  "))) == 1

    def test_no_match_gives_empty_ledger(self, ledger):
        assert len(ledger.filter_by(TextSearchFilter("pizza"))) == 0

    @pytest.mark.parametrize("bad", ["", "   ", None, 42])
    def test_empty_or_non_text_is_rejected(self, bad):
        with pytest.raises(ValidationError):
            TextSearchFilter(bad)


class TestCombining:
    """&, | and ~ build bigger filters from small ones."""

    def test_and(self, ledger):
        september_tesco = DateRangeFilter.for_month(2026, 9) & TextSearchFilter("tesco")
        assert names(ledger.filter_by(september_tesco)) == ["Weekly shop at TESCO"]

    def test_or(self, ledger):
        rent_or_coffee = TextSearchFilter("rent") | TextSearchFilter("flat white")
        assert names(ledger.filter_by(rent_or_coffee)) == ["Rent", "Flat white"]

    def test_not(self, ledger):
        assert len(ledger.filter_by(~TypeFilter(Expense))) == 2

    def test_mixed(self, ledger):
        # Food spending that is NOT from Tesco.
        food = CategoryFilter(Category.GROCERIES, Category.EATING_OUT)
        result = ledger.filter_by(food & ~TextSearchFilter("tesco"))
        assert names(result) == ["Flat white"]

    def test_combined_filters_are_still_filters(self):
        combined = TextSearchFilter("a") & TextSearchFilter("b")
        assert isinstance(combined, TransactionFilter)

    def test_joining_with_non_filter_fails(self):
        with pytest.raises(TypeError):
            TextSearchFilter("a") & "b"

    def test_filtering_does_not_change_the_original(self, ledger):
        ledger.filter_by(TextSearchFilter("rent"))
        assert len(ledger) == 6

    def test_filters_chain(self, ledger):
        result = ledger.filter_by(TypeFilter(Expense)).filter_by(AmountRangeFilter(maximum=10))
        assert names(result) == ["Flat white"]

    def test_filtered_ledger_still_has_totals(self, ledger):
        september = ledger.filter_by(DateRangeFilter.for_month(2026, 9))
        assert str(september.total_expenses) == "940.75"


class TestAllOf:

    def test_no_filters_matches_everything(self, ledger):
        assert len(ledger.filter_by(all_of())) == len(ledger)

    def test_joins_with_and(self, ledger):
        chosen = all_of(TypeFilter(Expense), TextSearchFilter("tesco"),
                        AmountRangeFilter(minimum=50))
        assert names(ledger.filter_by(chosen)) == ["Weekly shop at TESCO"]

    def test_match_all(self, ledger):
        assert len(ledger.filter_by(MatchAll())) == len(ledger)


class TestBaseClass:

    def test_cannot_be_created(self):
        with pytest.raises(TypeError):
            TransactionFilter()

    def test_filters_are_callable(self, ledger):
        assert TextSearchFilter("rent")(ledger[1]) is True

    def test_repr_is_readable(self):
        text = repr(TextSearchFilter("rent") & ~TypeFilter(Income))
        assert "TextSearchFilter" in text and "TypeFilter(Income)" in text
