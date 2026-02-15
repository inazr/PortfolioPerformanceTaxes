"""Tests für Netto-Verkaufsplanung."""

from datetime import date
from decimal import Decimal

import pytest

from pptax.models.portfolio import Security, FondsTyp
from pptax.engine.fifo import FifoBestand
from pptax.engine.verkauf import plane_netto_verkauf, pruefe_erreichbarkeit


def _make_position(uuid, kaufdatum, stuecke, kurs):
    fifo = FifoBestand(uuid)
    fifo.kauf(kaufdatum, stuecke, kurs)
    return fifo


class TestVerkaufsplanung:
    def test_einfacher_verkauf(self):
        """Einfacher Verkauf ohne Freibetrag-Nutzung."""
        sec = Security(uuid="s1", name="ETF", isin="IE001", fonds_typ=FondsTyp.AKTIENFONDS)
        fifo = _make_position("s1", date(2020, 1, 1), Decimal("100"), Decimal("50"))

        plan = plane_netto_verkauf(
            ziel_netto=Decimal("1000"),
            jahr=2023,
            veranlagungstyp="single",
            freibetrag_genutzt=Decimal("1000"),  # voll genutzt
            positionen={"s1": fifo},
            aktuelle_kurse={"s1": Decimal("100")},
            securities={"s1": sec},
        )
        assert plan.erreichtes_netto > Decimal("0")
        assert len(plan.verkaufsplan) > 0

    def test_verkauf_mit_freibetrag(self):
        """Verkauf mit verbleibendem Freibetrag."""
        sec = Security(uuid="s1", name="ETF", isin="IE001", fonds_typ=FondsTyp.AKTIENFONDS)
        fifo = _make_position("s1", date(2020, 1, 1), Decimal("100"), Decimal("50"))

        plan = plane_netto_verkauf(
            ziel_netto=Decimal("500"),
            jahr=2023,
            veranlagungstyp="single",
            freibetrag_genutzt=Decimal("0"),
            positionen={"s1": fifo},
            aktuelle_kurse={"s1": Decimal("100")},
            securities={"s1": sec},
        )
        # Weniger Steuer dank Freibetrag
        assert plan.steuer_gesamt < plan.brutto_gesamt * Decimal("0.26375")

    def test_multi_lot_fifo(self):
        """Verkauf über mehrere FIFO-Lots."""
        sec = Security(uuid="s1", name="ETF", isin="IE001", fonds_typ=FondsTyp.AKTIENFONDS)
        fifo = FifoBestand("s1")
        fifo.kauf(date(2019, 1, 1), Decimal("10"), Decimal("40"))
        fifo.kauf(date(2020, 1, 1), Decimal("10"), Decimal("60"))

        plan = plane_netto_verkauf(
            ziel_netto=Decimal("1500"),
            jahr=2023,
            veranlagungstyp="single",
            freibetrag_genutzt=Decimal("1000"),
            positionen={"s1": fifo},
            aktuelle_kurse={"s1": Decimal("100")},
            securities={"s1": sec},
        )
        assert len(plan.verkaufsplan) >= 1

    def test_erreichbarkeit(self):
        """Prüfe Erreichbarkeit des Zielbetrags."""
        fifo = FifoBestand("s1")
        fifo.kauf(date(2020, 1, 1), Decimal("10"), Decimal("50"))

        assert pruefe_erreichbarkeit(
            Decimal("500"), {"s1": fifo}, {"s1": Decimal("100")}
        )
        assert not pruefe_erreichbarkeit(
            Decimal("2000"), {"s1": fifo}, {"s1": Decimal("100")}
        )
