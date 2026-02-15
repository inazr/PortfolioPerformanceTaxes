"""Tests für FIFO-Bestandsführung."""

from datetime import date
from decimal import Decimal

import pytest

from pptax.engine.fifo import FifoBestand


class TestFifoBestand:
    def test_einfacher_kauf_verkauf(self):
        """Einfacher Kauf und kompletter Verkauf."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2022, 1, 15), Decimal("100"), Decimal("50.00"))

        positionen = fifo.verkauf(date(2023, 6, 1), Decimal("100"), Decimal("60.00"))
        assert len(positionen) == 1
        assert positionen[0].stuecke == Decimal("100")
        assert positionen[0].gewinn_brutto == Decimal("1000.00")
        assert fifo.gesamtstuecke() == Decimal("0")

    def test_teilverkauf(self):
        """Teilverkauf eines Lots."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2022, 1, 15), Decimal("100"), Decimal("50.00"))

        positionen = fifo.verkauf(date(2023, 6, 1), Decimal("30"), Decimal("60.00"))
        assert len(positionen) == 1
        assert positionen[0].stuecke == Decimal("30")
        assert positionen[0].gewinn_brutto == Decimal("300.00")
        assert fifo.gesamtstuecke() == Decimal("70")

    def test_fifo_reihenfolge(self):
        """FIFO: ältestes Lot wird zuerst verkauft."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2021, 1, 1), Decimal("50"), Decimal("40.00"))
        fifo.kauf(date(2022, 1, 1), Decimal("50"), Decimal("60.00"))

        positionen = fifo.verkauf(date(2023, 6, 1), Decimal("50"), Decimal("70.00"))
        assert len(positionen) == 1
        # Erstes Lot (Einstand 40) wird verkauft
        assert positionen[0].einstandskurs == Decimal("40.00")
        assert positionen[0].gewinn_brutto == Decimal("1500.00")

    def test_cross_lot_verkauf(self):
        """Verkauf über mehrere Lots hinweg."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2021, 1, 1), Decimal("30"), Decimal("40.00"))
        fifo.kauf(date(2022, 1, 1), Decimal("30"), Decimal("60.00"))

        positionen = fifo.verkauf(date(2023, 6, 1), Decimal("50"), Decimal("70.00"))
        assert len(positionen) == 2
        # Lot 1: 30 Stücke à 40 -> Gewinn 900
        assert positionen[0].stuecke == Decimal("30")
        assert positionen[0].einstandskurs == Decimal("40.00")
        # Lot 2: 20 Stücke à 60 -> Gewinn 200
        assert positionen[1].stuecke == Decimal("20")
        assert positionen[1].einstandskurs == Decimal("60.00")

    def test_vorabpauschale_anrechnung(self):
        """Vorabpauschalen werden bei Verkauf angerechnet."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2022, 1, 1), Decimal("100"), Decimal("50.00"))
        fifo.add_vorabpauschale(Decimal("50.00"))

        positionen = fifo.verkauf(date(2023, 6, 1), Decimal("100"), Decimal("60.00"))
        assert positionen[0].vorabpauschalen_angerechnet == Decimal("50.00")

    def test_insufficient_shares_raises(self):
        """Verkauf von mehr als verfügbar -> ValueError."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2022, 1, 1), Decimal("50"), Decimal("50.00"))

        with pytest.raises(ValueError, match="Nicht genügend Stücke"):
            fifo.verkauf(date(2023, 6, 1), Decimal("100"), Decimal("60.00"))

    def test_gewinn_bei_verkauf_simulation(self):
        """Simulation ohne Bestand zu verändern."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2022, 1, 1), Decimal("100"), Decimal("50.00"))

        gewinn = fifo.gewinn_bei_verkauf(Decimal("50"), Decimal("60.00"))
        assert gewinn == Decimal("500.00")
        # Bestand unverändert
        assert fifo.gesamtstuecke() == Decimal("100")

    def test_verlust(self):
        """Verkauf mit Verlust."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2022, 1, 1), Decimal("100"), Decimal("60.00"))

        positionen = fifo.verkauf(date(2023, 6, 1), Decimal("100"), Decimal("50.00"))
        assert positionen[0].gewinn_brutto == Decimal("-1000.00")
