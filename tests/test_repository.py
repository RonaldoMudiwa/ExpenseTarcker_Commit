"""Tests for saving and loading.

tmp_path gives each test its own empty folder, so the real data is never touched.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from expense_tracker import (
    Category,
    Expense,
    Income,
    IncomeSource,
    InMemoryTransactionRepository,
    JSONTransactionRepository,
    PaymentMethod,
    SerializationError,
    StorageError,
    Transaction,
    TransactionFactory,
    TransactionLedger,
    TransactionRepository,
)


@pytest.fixture
def ledger() -> TransactionLedger:
    return TransactionLedger(
        [
            Income("2400.00", "Salary", IncomeSource.SALARY, "2026-09-01",
                   is_recurring=True),
            Expense("875.00", "Rent", Category.HOUSING, "2026-09-02",
                    PaymentMethod.BANK_TRANSFER),
            Expense("3.40", "Flat white", Category.EATING_OUT, "2026-09-08"),
        ]
    )


@pytest.fixture
def json_path(tmp_path):
    return tmp_path / "transactions.json"


@pytest.fixture
def repo(json_path) -> JSONTransactionRepository:
    return JSONTransactionRepository(json_path)


def write_json(path, document) -> None:
    """Put a hand made document on disk, for testing bad files."""
    path.write_text(json.dumps(document), encoding="utf-8")


class TestFactory:
    """Building the right class from a saved record."""

    def test_default_knows_expense_and_income(self):
        assert set(TransactionFactory.default().known_types) == {"expense", "income"}

    def test_builds_expense(self):
        record = Expense("3.40", "Coffee", "eating out").to_dict()
        assert isinstance(TransactionFactory.default().from_dict(record), Expense)

    def test_builds_income(self):
        record = Income("50", "Gift", "gift").to_dict()
        assert isinstance(TransactionFactory.default().from_dict(record), Income)

    def test_missing_type_is_rejected(self):
        with pytest.raises(SerializationError, match="type"):
            TransactionFactory.default().from_dict({"amount": "1", "description": "x"})

    def test_unknown_type_is_rejected(self):
        with pytest.raises(SerializationError, match="Unknown transaction type"):
            TransactionFactory.default().from_dict({"type": "transfer"})

    def test_non_dict_record_is_rejected(self):
        with pytest.raises(SerializationError):
            TransactionFactory.default().from_dict(["not", "a", "dict"])

    def test_registering_same_type_twice_is_rejected(self):
        factory = TransactionFactory.default()
        with pytest.raises(ValueError):
            factory.register(Expense)

    def test_new_types_can_be_registered(self):
        """A new transaction type plugs in without editing the factory."""

        class Transfer(Transaction):
            TRANSACTION_TYPE = "transfer"

            @property
            def signed_amount(self) -> Decimal:
                return Decimal("0.00")

            def summary_line(self) -> str:
                return self.description

            @classmethod
            def from_dict(cls, data):
                return cls(data["amount"], data["description"])

        factory = TransactionFactory()
        factory.register(Transfer)
        built = factory.from_dict({"type": "transfer", "amount": "10",
                                   "description": "To savings"})
        assert isinstance(built, Transfer)


class TestRoundTrip:
    """Whatever goes in must come back out the same."""

    def test_missing_file_loads_as_empty(self, repo):
        assert len(repo.load()) == 0

    def test_save_creates_the_file(self, repo, json_path, ledger):
        repo.save(ledger)
        assert json_path.exists()

    def test_save_creates_missing_folders(self, tmp_path, ledger):
        repo = JSONTransactionRepository(tmp_path / "a" / "b" / "data.json")
        repo.save(ledger)
        assert repo.path.exists()

    def test_same_transactions_come_back(self, repo, ledger):
        repo.save(ledger)
        assert list(repo.load()) == list(ledger)

    def test_order_is_kept(self, repo, ledger):
        repo.save(ledger)
        loaded = repo.load()
        assert [t.description for t in loaded] == [t.description for t in ledger]

    def test_balance_is_exact_after_reload(self, repo, ledger):
        repo.save(ledger)
        assert repo.load().balance == Decimal("1521.60")

    def test_every_field_survives(self, repo, ledger):
        repo.save(ledger)
        salary, rent, _ = repo.load()
        assert salary.source is IncomeSource.SALARY
        assert salary.is_recurring is True
        assert rent.category is Category.HOUSING
        assert rent.payment_method is PaymentMethod.BANK_TRANSFER
        assert rent.transaction_date.isoformat() == "2026-09-02"

    def test_save_replaces_old_contents(self, repo, ledger):
        repo.save(ledger)
        repo.save(ledger[:1])
        assert len(repo.load()) == 1

    def test_empty_ledger_round_trips(self, repo):
        repo.save(TransactionLedger())
        assert len(repo.load()) == 0

    def test_amounts_stored_as_text(self, repo, json_path, ledger):
        # Text keeps pennies exact. A JSON number could come back as a float.
        repo.save(ledger)
        stored = json.loads(json_path.read_text(encoding="utf-8"))
        assert stored["transactions"][0]["amount"] == "2400.00"

    def test_file_has_version(self, repo, json_path, ledger):
        repo.save(ledger)
        stored = json.loads(json_path.read_text(encoding="utf-8"))
        assert stored["version"] == 1

    def test_no_temp_files_left_behind(self, repo, tmp_path, ledger):
        repo.save(ledger)
        repo.save(ledger)
        assert [p.name for p in tmp_path.iterdir()] == ["transactions.json"]


class TestBadFiles:
    """A damaged file gives a clear StorageError."""

    def test_not_json(self, repo, json_path):
        json_path.write_text("{ this is not json", encoding="utf-8")
        with pytest.raises(StorageError, match="not valid JSON"):
            repo.load()

    def test_top_level_list(self, repo, json_path):
        write_json(json_path, [])
        with pytest.raises(StorageError, match="JSON object"):
            repo.load()

    def test_wrong_version(self, repo, json_path):
        write_json(json_path, {"version": 99, "transactions": []})
        with pytest.raises(StorageError, match="version"):
            repo.load()

    def test_missing_transactions_list(self, repo, json_path):
        write_json(json_path, {"version": 1})
        with pytest.raises(StorageError, match="transactions"):
            repo.load()

    def test_record_with_unknown_type(self, repo, json_path):
        write_json(json_path, {"version": 1, "transactions": [{"type": "loan"}]})
        with pytest.raises(StorageError, match="bad record"):
            repo.load()

    def test_record_with_bad_amount(self, repo, json_path):
        record = {"type": "expense", "amount": "-5", "description": "Oops"}
        write_json(json_path, {"version": 1, "transactions": [record]})
        with pytest.raises(StorageError):
            repo.load()

    def test_duplicate_ids_in_file(self, repo, json_path):
        record = Expense("1", "Gum").to_dict()
        write_json(json_path, {"version": 1, "transactions": [record, record]})
        with pytest.raises(StorageError):
            repo.load()

    def test_original_error_is_kept(self, repo, json_path):
        write_json(json_path, {"version": 1, "transactions": [{"type": "loan"}]})
        with pytest.raises(StorageError) as caught:
            repo.load()
        assert isinstance(caught.value.__cause__, SerializationError)


class TestInMemory:
    """Should behave just like the file version."""

    def test_starts_empty(self):
        assert len(InMemoryTransactionRepository().load()) == 0

    def test_round_trip(self, ledger):
        repo = InMemoryTransactionRepository()
        repo.save(ledger)
        assert list(repo.load()) == list(ledger)

    def test_saved_copy_is_not_changed_by_later_edits(self, ledger):
        repo = InMemoryTransactionRepository()
        repo.save(ledger)
        ledger[0].description = "Changed after saving"
        assert repo.load()[0].description == "Salary"


class TestSwappable:
    """Any repository can stand in for any other."""

    @pytest.mark.parametrize("make_repo", [
        lambda tmp: JSONTransactionRepository(tmp / "t.json"),
        lambda tmp: InMemoryTransactionRepository(),
    ])
    def test_same_behaviour(self, make_repo, tmp_path, ledger):
        repo: TransactionRepository = make_repo(tmp_path)
        repo.save(ledger)
        assert repo.load().balance == ledger.balance

    def test_base_class_cannot_be_created(self):
        with pytest.raises(TypeError):
            TransactionRepository()
