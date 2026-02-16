"""Tests für Kurs-Utilities."""

from datetime import date
from decimal import Decimal

from pptax.engine.kurs_utils import build_kurse_map, find_nearest_kurs
from pptax.models.portfolio import HistorischerKurs


class TestBuildKurseMap:
    def test_basic(self):
        kurse = [
            HistorischerKurs("sec-1", date(2024, 1, 2), Decimal("100")),
            HistorischerKurs("sec-1", date(2024, 12, 30), Decimal("110")),
            HistorischerKurs("sec-2", date(2024, 1, 2), Decimal("50")),
        ]
        result = build_kurse_map(kurse)
        assert len(result) == 2
        assert result["sec-1"]["2024-01-02"] == Decimal("100")
        assert result["sec-1"]["2024-12-30"] == Decimal("110")
        assert result["sec-2"]["2024-01-02"] == Decimal("50")

    def test_empty(self):
        assert build_kurse_map([]) == {}


class TestFindNearestKurs:
    def test_exact_match(self):
        kurse = {"2024-01-01": Decimal("100")}
        assert find_nearest_kurs(kurse, date(2024, 1, 1)) == Decimal("100")

    def test_nearest_before(self):
        kurse = {"2023-12-29": Decimal("99")}
        assert find_nearest_kurs(kurse, date(2024, 1, 1)) == Decimal("99")

    def test_nearest_after(self):
        kurse = {"2024-01-03": Decimal("101")}
        assert find_nearest_kurs(kurse, date(2024, 1, 1)) == Decimal("101")

    def test_prefers_earlier_at_same_delta(self):
        """Bei gleichem Abstand wird der frühere Kurs bevorzugt."""
        kurse = {
            "2023-12-31": Decimal("99"),
            "2024-01-02": Decimal("101"),
        }
        assert find_nearest_kurs(kurse, date(2024, 1, 1)) == Decimal("99")

    def test_no_match_outside_delta(self):
        kurse = {"2024-01-10": Decimal("100")}
        assert find_nearest_kurs(kurse, date(2024, 1, 1)) is None

    def test_custom_max_delta(self):
        kurse = {"2024-01-10": Decimal("100")}
        assert find_nearest_kurs(kurse, date(2024, 1, 1), max_delta=10) == Decimal("100")

    def test_empty_kurse(self):
        assert find_nearest_kurs({}, date(2024, 1, 1)) is None
