"""Kurs-Lookup Utilities für Engine-Layer."""

from datetime import date, timedelta
from decimal import Decimal

from pptax.models.portfolio import HistorischerKurs


def build_kurse_map(
    kurse: list[HistorischerKurs],
) -> dict[str, dict[str, Decimal]]:
    """Baue eine verschachtelte Map: security_uuid -> datum_iso -> kurs."""
    result: dict[str, dict[str, Decimal]] = {}
    for k in kurse:
        if k.security_uuid not in result:
            result[k.security_uuid] = {}
        result[k.security_uuid][k.datum.isoformat()] = k.kurs
    return result


def find_nearest_kurs(
    kurse: dict[str, Decimal],
    target: date,
    max_delta: int = 5,
) -> Decimal | None:
    """Finde den nächsten Kurs zu einem Stichtag.

    Sucht zuerst exakten Match, dann innerhalb von max_delta Tagen.
    """
    if not kurse:
        return None
    target_str = target.isoformat()
    if target_str in kurse:
        return kurse[target_str]
    for delta in range(1, max_delta + 1):
        for d in [target - timedelta(days=delta), target + timedelta(days=delta)]:
            if d.isoformat() in kurse:
                return kurse[d.isoformat()]
    return None
