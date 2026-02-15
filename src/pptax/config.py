"""App-Konfiguration."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class AppConfig:
    """Globale Anwendungskonfiguration."""

    veranlagungstyp: str = "single"  # "single" oder "joint"
    kirchensteuer: bool = False
    bundesland: str = "default"
    freibetrag_bereits_genutzt: Decimal = Decimal("0")
