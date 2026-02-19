"""Datenmodelle für Steuerergebnisse."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class VorabpauschaleErgebnis:
    """Ergebnis der Vorabpauschale-Berechnung für ein Wertpapier und ein Jahr."""

    security_uuid: str
    jahr: int
    wert_jahresanfang: Decimal
    wert_jahresende: Decimal
    basiszins: Decimal
    basisertrag: Decimal
    wertsteigerung: Decimal
    ausschuettungen: Decimal
    vorabpauschale_brutto: Decimal
    teilfreistellung_satz: Decimal
    vorabpauschale_steuerpflichtig: Decimal
    steuer: Decimal


@dataclass
class VerkauftePosition:
    """Ein bei Verkauf aufgelöstes FIFO-Lot."""

    kaufdatum: date
    verkaufsdatum: date
    stuecke: Decimal
    einstandskurs: Decimal
    verkaufskurs: Decimal
    gewinn_brutto: Decimal
    vorabpauschalen_angerechnet: Decimal


@dataclass
class VerkaufsVorschlag:
    """Ein konkreter Verkaufsvorschlag."""

    security_uuid: str
    security_name: str
    isin: Optional[str]
    stuecke: Decimal
    kaufdatum: date
    einstandskurs: Decimal
    aktueller_kurs: Decimal
    brutto_erloes: Decimal
    gewinn_brutto: Decimal
    teilfreistellung_satz: Decimal
    gewinn_steuerpflichtig: Decimal
    steuer: Decimal
    netto_erloes: Decimal
    bestandsgeschuetzt: bool = False


@dataclass
class FreibetragOptimierungErgebnis:
    """Empfehlung zum Ausnutzen des Sparerpauschbetrags."""

    jahr: int
    freibetrag_gesamt: Decimal
    freibetrag_bereits_genutzt: Decimal
    freibetrag_verbleibend: Decimal
    verkaufsempfehlungen: list[VerkaufsVorschlag] = field(default_factory=list)


@dataclass
class NettoBetragPlan:
    """Verkaufsplan um einen Netto-Zielbetrag zu erhalten."""

    ziel_netto: Decimal
    erreichtes_netto: Decimal
    brutto_gesamt: Decimal
    steuer_gesamt: Decimal
    freibetrag_genutzt: Decimal
    verkaufsplan: list[VerkaufsVorschlag] = field(default_factory=list)


@dataclass
class VerlustverrechnungsErgebnis:
    """Ergebnis der Verlustverrechnung."""

    verlust_allgemein: Decimal = Decimal("0")
    verlust_aktien: Decimal = Decimal("0")
    verrechnet_allgemein: Decimal = Decimal("0")
    verrechnet_aktien: Decimal = Decimal("0")
    vortrag_allgemein: Decimal = Decimal("0")
    vortrag_aktien: Decimal = Decimal("0")
