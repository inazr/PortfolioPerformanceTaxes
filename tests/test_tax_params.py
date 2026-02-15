"""Tests für tax_params Lookup-Logik."""

from decimal import Decimal

import pytest

from pptax.engine.tax_params import get_param, get_gesamtsteuersatz


class TestGetParam:
    def test_exact_year(self):
        """Lookup für existierendes Jahr (exakt)."""
        result = get_param("basiszins_vorabpauschale", 2023)
        assert result == 0.0255

    def test_between_years(self):
        """Lookup für Jahr zwischen zwei Einträgen."""
        # sparerpauschbetrag hat 2009 und 2023
        result = get_param("sparerpauschbetrag", 2022)
        assert result == {"single": 801, "joint": 1602}

    def test_after_last_entry(self):
        """Lookup für Jahr nach dem letzten Eintrag."""
        result = get_param("sparerpauschbetrag", 2025)
        assert result == {"single": 1000, "joint": 2000}

    def test_before_first_entry_raises(self):
        """Lookup für Jahr vor dem ersten Eintrag -> ValueError."""
        with pytest.raises(ValueError, match="Kein gültiger Eintrag"):
            get_param("basiszins_vorabpauschale", 2017)

    def test_unknown_param_raises(self):
        with pytest.raises(ValueError, match="Unbekannter Parameter"):
            get_param("nonexistent_param", 2023)

    def test_basiszins_values(self):
        """Basiszins-Werte gegen bekannte Werte prüfen."""
        assert get_param("basiszins_vorabpauschale", 2023) == 0.0255
        assert get_param("basiszins_vorabpauschale", 2024) == 0.0229
        assert get_param("basiszins_vorabpauschale", 2021) == -0.0045

    def test_teilfreistellung(self):
        result = get_param("teilfreistellung", 2023)
        assert result["aktienfonds"] == 0.30
        assert result["mischfonds"] == 0.15
        assert result["sonstige"] == 0.00


class TestGetGesamtsteuersatz:
    def test_ohne_kirchensteuer(self):
        """Standard: KESt + Soli = 26,375%."""
        satz = get_gesamtsteuersatz(2023)
        expected = Decimal("0.25") + Decimal("0.25") * Decimal("0.055")
        assert satz == expected
        assert abs(satz - Decimal("0.26375")) < Decimal("0.00001")

    def test_mit_kirchensteuer_default(self):
        """Mit Kirchensteuer 9% (default)."""
        satz = get_gesamtsteuersatz(2023, kirchensteuer=True)
        # KESt_eff = 0.25 / (1 + 0.09 * 0.25) = 0.25 / 1.0225
        # Gesamtsatz > 26.375% wegen Kirchensteuer
        assert satz > Decimal("0.26375")
        assert satz < Decimal("0.30")  # aber unter 30%

    def test_mit_kirchensteuer_bayern(self):
        """Mit Kirchensteuer 8% (Bayern)."""
        satz = get_gesamtsteuersatz(2023, kirchensteuer=True, bundesland="bayern")
        satz_default = get_gesamtsteuersatz(2023, kirchensteuer=True)
        # Bayern hat niedrigeren Kirchensteuersatz -> niedrigerer Gesamtsatz
        assert satz < satz_default
