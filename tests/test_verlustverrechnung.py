"""Tests für Verlustverrechnung."""

from decimal import Decimal

from pptax.engine.verlustverrechnung import VerlustverrechnungsManager


class TestVerlustverrechnungsManager:
    def test_basic_offset(self):
        """Verlust wird mit Gewinn verrechnet."""
        mgr = VerlustverrechnungsManager()
        mgr.add_verlust(Decimal("500"))
        rest = mgr.add_gewinn(Decimal("800"))
        assert rest == Decimal("300")

    def test_verlust_groesser_gewinn(self):
        """Verlust größer als Gewinn → Rest bleibt als Vortrag."""
        mgr = VerlustverrechnungsManager()
        mgr.add_verlust(Decimal("1000"))
        rest = mgr.add_gewinn(Decimal("600"))
        assert rest == Decimal("0")
        vortrag_allg, vortrag_aktien = mgr.get_vortrag()
        assert vortrag_allg == Decimal("400")

    def test_separate_pools(self):
        """Aktien-Verluste nur mit Aktien-Gewinnen verrechenbar."""
        mgr = VerlustverrechnungsManager()
        mgr.add_verlust(Decimal("500"), ist_aktie=True)

        # Allgemeiner Gewinn: Aktien-Verlust wird NICHT verrechnet
        rest = mgr.add_gewinn(Decimal("800"), ist_aktie=False)
        assert rest == Decimal("800")

        # Aktien-Gewinn: Aktien-Verlust WIRD verrechnet
        rest = mgr.add_gewinn(Decimal("800"), ist_aktie=True)
        assert rest == Decimal("300")

    def test_multi_year_carryforward(self):
        """Verluste werden ins Folgejahr vorgetragen."""
        mgr = VerlustverrechnungsManager()
        mgr.add_verlust(Decimal("1000"))
        mgr.add_gewinn(Decimal("300"))

        erg = mgr.jahresabschluss()
        assert erg.vortrag_allgemein == Decimal("700")

        # Im neuen Jahr: Vortrag wird weiter genutzt
        rest = mgr.add_gewinn(Decimal("500"))
        assert rest == Decimal("0")
        vortrag_allg, _ = mgr.get_vortrag()
        assert vortrag_allg == Decimal("200")

    def test_aktien_und_allgemein(self):
        """Aktien-Gewinne können auch mit allgemeinen Verlusten verrechnet werden."""
        mgr = VerlustverrechnungsManager()
        mgr.add_verlust(Decimal("500"), ist_aktie=False)

        # Aktien-Gewinn wird mit allgemeinem Verlust verrechnet
        rest = mgr.add_gewinn(Decimal("800"), ist_aktie=True)
        assert rest == Decimal("300")
