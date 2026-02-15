"""Tests für Freibetrag-Optimierung."""

from datetime import date
from decimal import Decimal

import pytest

from pptax.models.portfolio import Security, FondsTyp
from pptax.engine.fifo import FifoBestand
from pptax.engine.freibetrag import optimiere_freibetrag


def _make_position(uuid, kaufdatum, stuecke, kurs):
    fifo = FifoBestand(uuid)
    fifo.kauf(kaufdatum, stuecke, kurs)
    return fifo


class TestFreibetragOptimierung:
    def test_freibetrag_voll_ausschoepfen(self):
        """Freibetrag vollständig ausschöpfen."""
        sec = Security(uuid="s1", name="ETF", isin="IE001", fonds_typ=FondsTyp.AKTIENFONDS)
        fifo = _make_position("s1", date(2020, 1, 1), Decimal("1000"), Decimal("50"))

        result = optimiere_freibetrag(
            jahr=2023,
            veranlagungstyp="single",
            bereits_genutzt=Decimal("0"),
            positionen={"s1": fifo},
            aktuelle_kurse={"s1": Decimal("100")},
            securities={"s1": sec},
        )
        assert result.freibetrag_gesamt == Decimal("1000")
        assert result.freibetrag_verbleibend == Decimal("1000")
        assert len(result.verkaufsempfehlungen) > 0
        # Steuer soll 0 sein (innerhalb Freibetrag)
        for v in result.verkaufsempfehlungen:
            assert v.steuer == Decimal("0")

    def test_freibetrag_teilweise_genutzt(self):
        """Freibetrag teilweise bereits genutzt."""
        sec = Security(uuid="s1", name="ETF", isin="IE001", fonds_typ=FondsTyp.AKTIENFONDS)
        fifo = _make_position("s1", date(2020, 1, 1), Decimal("1000"), Decimal("50"))

        result = optimiere_freibetrag(
            jahr=2023,
            veranlagungstyp="single",
            bereits_genutzt=Decimal("800"),
            positionen={"s1": fifo},
            aktuelle_kurse={"s1": Decimal("100")},
            securities={"s1": sec},
        )
        assert result.freibetrag_verbleibend == Decimal("200")

    def test_keine_gewinne(self):
        """Keine Gewinne vorhanden."""
        sec = Security(uuid="s1", name="ETF", isin="IE001", fonds_typ=FondsTyp.AKTIENFONDS)
        fifo = _make_position("s1", date(2020, 1, 1), Decimal("100"), Decimal("100"))

        result = optimiere_freibetrag(
            jahr=2023,
            veranlagungstyp="single",
            bereits_genutzt=Decimal("0"),
            positionen={"s1": fifo},
            aktuelle_kurse={"s1": Decimal("90")},  # Verlust
            securities={"s1": sec},
        )
        assert len(result.verkaufsempfehlungen) == 0

    def test_freibetrag_bereits_voll(self):
        """Freibetrag bereits voll genutzt."""
        sec = Security(uuid="s1", name="ETF", isin="IE001", fonds_typ=FondsTyp.AKTIENFONDS)
        fifo = _make_position("s1", date(2020, 1, 1), Decimal("100"), Decimal("50"))

        result = optimiere_freibetrag(
            jahr=2023,
            veranlagungstyp="single",
            bereits_genutzt=Decimal("1000"),
            positionen={"s1": fifo},
            aktuelle_kurse={"s1": Decimal("100")},
            securities={"s1": sec},
        )
        assert result.freibetrag_verbleibend == Decimal("0")
        assert len(result.verkaufsempfehlungen) == 0

    def test_verschiedene_tfs(self):
        """Verschiedene Teilfreistellungssätze: Aktienfonds hat höhere TFS."""
        sec_aktien = Security(uuid="s1", name="Aktien", isin="IE001", fonds_typ=FondsTyp.AKTIENFONDS)
        sec_sonstige = Security(uuid="s2", name="Sonstige", isin="IE002", fonds_typ=FondsTyp.SONSTIGE)

        fifo1 = _make_position("s1", date(2020, 1, 1), Decimal("100"), Decimal("50"))
        fifo2 = _make_position("s2", date(2020, 1, 1), Decimal("100"), Decimal("50"))

        result = optimiere_freibetrag(
            jahr=2023,
            veranlagungstyp="single",
            bereits_genutzt=Decimal("0"),
            positionen={"s1": fifo1, "s2": fifo2},
            aktuelle_kurse={"s1": Decimal("100"), "s2": Decimal("100")},
            securities={"s1": sec_aktien, "s2": sec_sonstige},
        )
        # Sonstige (TFS 0%) hat höheren stpfl. Gewinn pro Stück -> wird bevorzugt
        assert len(result.verkaufsempfehlungen) >= 1
        assert result.verkaufsempfehlungen[0].security_uuid == "s2"
