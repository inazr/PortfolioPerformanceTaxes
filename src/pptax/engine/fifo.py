"""FIFO-Bestandsführung gem. § 20 Abs. 4 Satz 7 EStG."""

import copy
from datetime import date
from decimal import Decimal

from pptax.models.portfolio import FifoPosition
from pptax.models.tax import VerkauftePosition


class FifoBestand:
    """Verwaltet FIFO-Bestände für ein einzelnes Wertpapier."""

    def __init__(self, security_uuid: str):
        self.security_uuid = security_uuid
        self._lots: list[FifoPosition] = []

    def kauf(self, datum: date, stuecke: Decimal, kurs: Decimal) -> None:
        """Fügt ein neues Kauflot hinzu."""
        self._lots.append(
            FifoPosition(
                kaufdatum=datum,
                stuecke=stuecke,
                einstandskurs=kurs,
                security_uuid=self.security_uuid,
            )
        )

    def verkauf(
        self, datum: date, stuecke: Decimal, aktueller_kurs: Decimal
    ) -> list[VerkauftePosition]:
        """Verkaufe FIFO-konform und gibt die verkauften Lots mit Gewinn zurück.

        Vorabpauschalen werden bei Gewinnermittlung angerechnet
        (§ 19 Abs. 1 Satz 3 InvStG).
        """
        if stuecke > self.gesamtstuecke():
            raise ValueError(
                f"Nicht genügend Stücke: {stuecke} angefordert, "
                f"{self.gesamtstuecke()} verfügbar"
            )

        verbleibend = stuecke
        ergebnis: list[VerkauftePosition] = []

        while verbleibend > 0 and self._lots:
            lot = self._lots[0]
            verkauft = min(verbleibend, lot.stuecke)
            anteil = verkauft / lot.stuecke if lot.stuecke > 0 else Decimal("1")

            gewinn_brutto = verkauft * (aktueller_kurs - lot.einstandskurs)
            vp_angerechnet = lot.vorabpauschalen_kumuliert * anteil

            ergebnis.append(
                VerkauftePosition(
                    kaufdatum=lot.kaufdatum,
                    verkaufsdatum=datum,
                    stuecke=verkauft,
                    einstandskurs=lot.einstandskurs,
                    verkaufskurs=aktueller_kurs,
                    gewinn_brutto=gewinn_brutto,
                    vorabpauschalen_angerechnet=vp_angerechnet,
                )
            )

            if verkauft >= lot.stuecke:
                self._lots.pop(0)
            else:
                rest_anteil = (lot.stuecke - verkauft) / lot.stuecke
                lot.vorabpauschalen_kumuliert = (
                    lot.vorabpauschalen_kumuliert * rest_anteil
                )
                lot.stuecke -= verkauft

            verbleibend -= verkauft

        return ergebnis

    def bestand(self) -> list[FifoPosition]:
        """Aktueller Bestand aller offenen Lots."""
        return list(self._lots)

    def gesamtstuecke(self) -> Decimal:
        """Gesamtzahl aller Stücke im Bestand."""
        return sum((lot.stuecke for lot in self._lots), Decimal("0"))

    def gewinn_bei_verkauf(
        self, stuecke: Decimal, aktueller_kurs: Decimal
    ) -> Decimal:
        """Simuliert Verkauf ohne Bestand zu verändern. Gibt Brutto-Gewinn zurück."""
        # Erstelle tiefe Kopie und simuliere
        sim = FifoBestand(self.security_uuid)
        sim._lots = copy.deepcopy(self._lots)
        positionen = sim.verkauf(date.today(), stuecke, aktueller_kurs)
        return sum(
            (p.gewinn_brutto - p.vorabpauschalen_angerechnet for p in positionen),
            Decimal("0"),
        )

    def add_vorabpauschale(self, betrag: Decimal) -> None:
        """Verteile Vorabpauschale proportional auf alle Lots."""
        gesamt = self.gesamtstuecke()
        if gesamt == 0:
            return
        for lot in self._lots:
            anteil = lot.stuecke / gesamt
            lot.vorabpauschalen_kumuliert += betrag * anteil
