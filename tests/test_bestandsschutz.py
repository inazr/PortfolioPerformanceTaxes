"""Tests für Bestandsschutz (Altaktien vor 01.01.2009)."""

from datetime import date
from decimal import Decimal

import pytest

from pptax.engine.bestandsschutz import ist_bestandsgeschuetzt
from pptax.engine.fifo import FifoBestand
from pptax.engine.freibetrag import optimiere_freibetrag
from pptax.engine.verkauf import plane_netto_verkauf
from pptax.models.portfolio import Security, FondsTyp


# --- Helper-Funktion ---


class TestIstBestandsgeschuetzt:
    def test_aktie_vor_2009_ist_geschuetzt(self):
        assert ist_bestandsgeschuetzt(date(2008, 12, 31), is_fond=False) is True

    def test_fond_vor_2009_nicht_geschuetzt(self):
        assert ist_bestandsgeschuetzt(date(2008, 6, 15), is_fond=True) is False

    def test_aktie_nach_2009_nicht_geschuetzt(self):
        assert ist_bestandsgeschuetzt(date(2009, 1, 1), is_fond=False) is False

    def test_aktie_genau_stichtag_nicht_geschuetzt(self):
        """01.01.2009 ist NICHT mehr bestandsgeschützt (< nicht <=)."""
        assert ist_bestandsgeschuetzt(date(2009, 1, 1), is_fond=False) is False

    def test_fond_nach_2009_nicht_geschuetzt(self):
        assert ist_bestandsgeschuetzt(date(2022, 3, 15), is_fond=True) is False


# --- Fixtures ---


@pytest.fixture
def altaktie():
    """Einzelaktie (kein Fond)."""
    return Security(
        uuid="alt-001",
        name="Altaktie AG",
        isin="DE000ALT0001",
        fonds_typ=FondsTyp.SONSTIGE,
        is_fond=False,
    )


@pytest.fixture
def altfond():
    """Fond, der auch vor 2009 gekauft wurde."""
    return Security(
        uuid="alt-002",
        name="Altfonds",
        isin="DE000ALT0002",
        fonds_typ=FondsTyp.AKTIENFONDS,
        is_fond=True,
    )


@pytest.fixture
def neuaktie():
    """Einzelaktie nach 2009 gekauft."""
    return Security(
        uuid="neu-001",
        name="Neuaktie AG",
        isin="DE000NEU0001",
        fonds_typ=FondsTyp.SONSTIGE,
        is_fond=False,
    )


def _make_fifo(uuid: str, kaufdatum: date, stuecke: Decimal, kurs: Decimal) -> FifoBestand:
    fifo = FifoBestand(uuid)
    fifo.kauf(kaufdatum, stuecke, kurs)
    return fifo


# --- Freibetrag-Optimierung ---


class TestFreibetragBestandsschutz:
    def test_altaktie_wird_uebersprungen(self, altaktie):
        """Bestandsgeschützte Lots werden bei Freibetrag-Optimierung ignoriert."""
        positionen = {
            altaktie.uuid: _make_fifo(altaktie.uuid, date(2007, 5, 10), Decimal("50"), Decimal("30")),
        }
        aktuelle_kurse = {altaktie.uuid: Decimal("100")}
        securities = {altaktie.uuid: altaktie}

        ergebnis = optimiere_freibetrag(
            jahr=2025,
            veranlagungstyp="single",
            bereits_genutzt=Decimal("0"),
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=securities,
        )

        assert len(ergebnis.verkaufsempfehlungen) == 0

    def test_fond_vor_2009_wird_nicht_uebersprungen(self, altfond):
        """Fonds vor 2009 haben KEINEN Bestandsschutz."""
        positionen = {
            altfond.uuid: _make_fifo(altfond.uuid, date(2007, 5, 10), Decimal("50"), Decimal("30")),
        }
        aktuelle_kurse = {altfond.uuid: Decimal("100")}
        securities = {altfond.uuid: altfond}

        ergebnis = optimiere_freibetrag(
            jahr=2025,
            veranlagungstyp="single",
            bereits_genutzt=Decimal("0"),
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=securities,
        )

        assert len(ergebnis.verkaufsempfehlungen) > 0


# --- Verkaufsplanung ---


class TestVerkaufBestandsschutz:
    def test_altaktie_steuerfrei(self, altaktie):
        """Bestandsgeschützte Lots: Steuer = 0, netto = brutto."""
        positionen = {
            altaktie.uuid: _make_fifo(altaktie.uuid, date(2007, 5, 10), Decimal("100"), Decimal("30")),
        }
        aktuelle_kurse = {altaktie.uuid: Decimal("100")}
        securities = {altaktie.uuid: altaktie}

        plan = plane_netto_verkauf(
            ziel_netto=Decimal("5000"),
            jahr=2025,
            veranlagungstyp="single",
            freibetrag_genutzt=Decimal("0"),
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=securities,
        )

        assert len(plan.verkaufsplan) == 1
        vorschlag = plan.verkaufsplan[0]
        assert vorschlag.bestandsgeschuetzt is True
        assert vorschlag.steuer == Decimal("0")
        assert vorschlag.netto_erloes == vorschlag.brutto_erloes

    def test_fond_vor_2009_wird_besteuert(self, altfond):
        """Fonds vor 2009: normaler Steuersatz (kein Bestandsschutz)."""
        positionen = {
            altfond.uuid: _make_fifo(altfond.uuid, date(2007, 5, 10), Decimal("100"), Decimal("30")),
        }
        aktuelle_kurse = {altfond.uuid: Decimal("100")}
        securities = {altfond.uuid: altfond}

        plan = plane_netto_verkauf(
            ziel_netto=Decimal("5000"),
            jahr=2025,
            veranlagungstyp="single",
            freibetrag_genutzt=Decimal("1000"),
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=securities,
        )

        assert len(plan.verkaufsplan) >= 1
        vorschlag = plan.verkaufsplan[0]
        assert vorschlag.bestandsgeschuetzt is False

    def test_neuaktie_wird_besteuert(self, neuaktie):
        """Aktien nach 2009: normal besteuert."""
        positionen = {
            neuaktie.uuid: _make_fifo(neuaktie.uuid, date(2022, 3, 15), Decimal("100"), Decimal("30")),
        }
        aktuelle_kurse = {neuaktie.uuid: Decimal("100")}
        securities = {neuaktie.uuid: neuaktie}

        plan = plane_netto_verkauf(
            ziel_netto=Decimal("5000"),
            jahr=2025,
            veranlagungstyp="single",
            freibetrag_genutzt=Decimal("1000"),
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=securities,
        )

        assert len(plan.verkaufsplan) >= 1
        vorschlag = plan.verkaufsplan[0]
        assert vorschlag.bestandsgeschuetzt is False
        # Freibetrag already used, so there should be tax on gains
        assert vorschlag.steuer > Decimal("0")

    def test_altaktie_verbraucht_keinen_freibetrag(self, altaktie):
        """Bestandsgeschützte Lots verbrauchen keinen Freibetrag."""
        positionen = {
            altaktie.uuid: _make_fifo(altaktie.uuid, date(2007, 5, 10), Decimal("100"), Decimal("30")),
        }
        aktuelle_kurse = {altaktie.uuid: Decimal("100")}
        securities = {altaktie.uuid: altaktie}

        plan = plane_netto_verkauf(
            ziel_netto=Decimal("5000"),
            jahr=2025,
            veranlagungstyp="single",
            freibetrag_genutzt=Decimal("0"),
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=securities,
        )

        assert plan.freibetrag_genutzt == Decimal("0")
