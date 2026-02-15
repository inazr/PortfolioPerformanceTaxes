"""Tests für Vorabpauschale-Berechnung."""

from datetime import date
from decimal import Decimal

import pytest

from pptax.models.portfolio import Security, FondsTyp
from pptax.engine.vorabpauschale import berechne_vorabpauschale


def _sec(fonds_typ=FondsTyp.AKTIENFONDS):
    return Security(uuid="test", name="Test", fonds_typ=fonds_typ)


class TestVorabpauschale:
    def test_fall1_normal_positiv(self):
        """Fall 1: Normaler positiver Basiszins, Wertsteigerung > Basisertrag.

        Jahr 2023, Basiszins 2.55%, Aktienfonds (TFS 30%)
        Wert 1.1.: 10.000€, Wert 31.12.: 12.000€
        Basisertrag = 10000 × 0.0255 × 0.7 = 178.50
        Vorabpauschale = 178.50 (< Wertsteigerung 2000)
        Steuerpflichtig = 178.50 × 0.70 = 124.95
        Steuer = 124.95 × 0.26375 = 32.96
        """
        erg = berechne_vorabpauschale(
            _sec(), 2023, Decimal("10000"), Decimal("12000")
        )
        assert erg.basisertrag == Decimal("178.50")
        assert erg.vorabpauschale_brutto == Decimal("178.50")
        assert erg.vorabpauschale_steuerpflichtig == Decimal("124.95")
        assert erg.steuer == Decimal("32.96")

    def test_fall2_wertsteigerung_kleiner_basisertrag(self):
        """Fall 2: Wertsteigerung < Basisertrag."""
        erg = berechne_vorabpauschale(
            _sec(), 2023, Decimal("10000"), Decimal("10100")
        )
        assert erg.vorabpauschale_brutto == Decimal("100")

    def test_fall3_negativer_basiszins(self):
        """Fall 3: Negativer Basiszins (2021) → Vorabpauschale = 0."""
        erg = berechne_vorabpauschale(
            _sec(), 2021, Decimal("10000"), Decimal("12000")
        )
        assert erg.vorabpauschale_brutto == Decimal("0")
        assert erg.steuer == Decimal("0")

    def test_fall4_wertverlust(self):
        """Fall 4: Wertverlust → Vorabpauschale = 0."""
        erg = berechne_vorabpauschale(
            _sec(), 2023, Decimal("10000"), Decimal("9000")
        )
        assert erg.vorabpauschale_brutto == Decimal("0")
        assert erg.steuer == Decimal("0")

    def test_fall5_mit_ausschuettungen_voll(self):
        """Fall 5a: Ausschüttungen >= Basisertrag → Vorabpauschale = 0."""
        erg = berechne_vorabpauschale(
            _sec(), 2023, Decimal("10000"), Decimal("12000"),
            ausschuettungen=Decimal("200"),
        )
        assert erg.vorabpauschale_brutto == Decimal("0")

    def test_fall5_mit_ausschuettungen_teilweise(self):
        """Fall 5b: Ausschüttungen < Basisertrag → Differenz bleibt."""
        erg = berechne_vorabpauschale(
            _sec(), 2023, Decimal("10000"), Decimal("12000"),
            ausschuettungen=Decimal("100"),
        )
        assert erg.vorabpauschale_brutto == Decimal("78.50")

    def test_fall6_unterjaehrig(self):
        """Fall 6: Unterjähriger Kauf im März → nur 10/12 der Vorabpauschale."""
        erg = berechne_vorabpauschale(
            _sec(), 2023, Decimal("10000"), Decimal("12000"),
            kaufdatum=date(2023, 3, 15),
        )
        # 178.50 × 10/12 = 148.75
        assert erg.vorabpauschale_brutto == Decimal("148.75")

    def test_fall7_mischfonds(self):
        """Fall 7: Mischfonds (TFS 15%)."""
        erg = berechne_vorabpauschale(
            _sec(FondsTyp.MISCHFONDS), 2023, Decimal("10000"), Decimal("12000")
        )
        # Steuerpflichtig = 178.50 × 0.85 = 151.73
        assert erg.teilfreistellung_satz == Decimal("0.15")
        assert erg.vorabpauschale_steuerpflichtig == Decimal("151.72") or \
               erg.vorabpauschale_steuerpflichtig == Decimal("151.73")

    def test_fall7_sonstige(self):
        """Fall 7: Sonstige (TFS 0%)."""
        erg = berechne_vorabpauschale(
            _sec(FondsTyp.SONSTIGE), 2023, Decimal("10000"), Decimal("12000")
        )
        assert erg.teilfreistellung_satz == Decimal("0.00")
        # Volle Besteuerung
        assert erg.vorabpauschale_steuerpflichtig == erg.vorabpauschale_brutto
