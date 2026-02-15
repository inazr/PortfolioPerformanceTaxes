"""Datenmodelle für Portfolio-Daten."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class FondsTyp(Enum):
    """Fondstyp für Teilfreistellungsermittlung."""

    AKTIENFONDS = "aktienfonds"
    MISCHFONDS = "mischfonds"
    IMMOBILIENFONDS_INLAND = "immobilienfonds_inland"
    IMMOBILIENFONDS_AUSLAND = "immobilienfonds_ausland"
    SONSTIGE = "sonstige"


class TransaktionsTyp(Enum):
    KAUF = "kauf"
    VERKAUF = "verkauf"
    EINLIEFERUNG = "einlieferung"
    AUSLIEFERUNG = "auslieferung"
    DIVIDENDE = "dividende"


@dataclass
class Security:
    """Ein Wertpapier / ETF / Fonds."""

    uuid: str
    name: str
    isin: Optional[str] = None
    wkn: Optional[str] = None
    fonds_typ: FondsTyp = FondsTyp.AKTIENFONDS
    is_fond: bool = True


@dataclass
class Transaction:
    """Eine einzelne Transaktion."""

    datum: date
    typ: TransaktionsTyp
    security_uuid: str
    stuecke: Decimal
    kurs: Decimal
    gesamtbetrag: Decimal
    gebuehren: Decimal = Decimal("0")
    steuern: Decimal = Decimal("0")


@dataclass
class HistorischerKurs:
    """Kurs zu einem Stichtag."""

    security_uuid: str
    datum: date
    kurs: Decimal


@dataclass
class FifoPosition:
    """Eine einzelne FIFO-Position (ein Kauflot)."""

    kaufdatum: date
    stuecke: Decimal
    einstandskurs: Decimal
    security_uuid: str
    vorabpauschalen_kumuliert: Decimal = Decimal("0")
