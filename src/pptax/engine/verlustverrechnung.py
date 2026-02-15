"""Verlustverrechnungstöpfe gem. deutschem Steuerrecht."""

from decimal import Decimal

from pptax.models.tax import VerlustverrechnungsErgebnis


class VerlustverrechnungsManager:
    """Verwaltet die Verlustverrechnungstöpfe.

    Topf 1 (allgemein): Verluste aus Fondsverkäufen - verrechenbar mit allen
        positiven Kapitalerträgen.
    Topf 2 (aktien): Verluste aus Einzelaktienverkäufen - NUR verrechenbar
        mit Gewinnen aus Einzelaktienverkäufen.

    Verlustverrechnung erfolgt VOR dem Sparerpauschbetrag.
    """

    def __init__(self):
        self._verlust_allgemein = Decimal("0")
        self._verlust_aktien = Decimal("0")
        self._verrechnet_allgemein = Decimal("0")
        self._verrechnet_aktien = Decimal("0")

    def add_verlust(self, betrag: Decimal, ist_aktie: bool = False) -> None:
        """Verlust hinzufügen (betrag sollte positiv sein)."""
        betrag = abs(betrag)
        if ist_aktie:
            self._verlust_aktien += betrag
        else:
            self._verlust_allgemein += betrag

    def add_gewinn(self, betrag: Decimal, ist_aktie: bool = False) -> Decimal:
        """Gewinn hinzufügen und mit Verlusten verrechnen.

        Gibt den nach Verrechnung verbleibenden steuerpflichtigen Gewinn zurück.
        """
        betrag = abs(betrag)

        if ist_aktie:
            # Aktiengewinne zuerst mit Aktienverlusten verrechnen
            if self._verlust_aktien > 0:
                verrechnung = min(betrag, self._verlust_aktien)
                self._verlust_aktien -= verrechnung
                self._verrechnet_aktien += verrechnung
                betrag -= verrechnung

        # Dann mit allgemeinen Verlusten verrechnen
        if betrag > 0 and self._verlust_allgemein > 0:
            verrechnung = min(betrag, self._verlust_allgemein)
            self._verlust_allgemein -= verrechnung
            self._verrechnet_allgemein += verrechnung
            betrag -= verrechnung

        return betrag

    def get_vortrag(self) -> tuple[Decimal, Decimal]:
        """Gibt die verbleibenden Verlustvorträge zurück (allgemein, aktien)."""
        return self._verlust_allgemein, self._verlust_aktien

    def jahresabschluss(self) -> VerlustverrechnungsErgebnis:
        """Erstellt das Ergebnis und bereitet den Vortrag ins nächste Jahr vor."""
        ergebnis = VerlustverrechnungsErgebnis(
            verlust_allgemein=self._verlust_allgemein + self._verrechnet_allgemein,
            verlust_aktien=self._verlust_aktien + self._verrechnet_aktien,
            verrechnet_allgemein=self._verrechnet_allgemein,
            verrechnet_aktien=self._verrechnet_aktien,
            vortrag_allgemein=self._verlust_allgemein,
            vortrag_aktien=self._verlust_aktien,
        )
        # Reset Verrechnungszähler für nächstes Jahr, behalte Vorträge
        self._verrechnet_allgemein = Decimal("0")
        self._verrechnet_aktien = Decimal("0")
        return ergebnis
