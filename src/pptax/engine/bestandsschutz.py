"""Bestandsschutz für Altaktien (vor 01.01.2009)."""

from datetime import date

BESTANDSSCHUTZ_STICHTAG = date(2009, 1, 1)


def ist_bestandsgeschuetzt(kaufdatum: date, is_fond: bool) -> bool:
    """Prüfe ob eine Position bestandsgeschützt ist (steuerfrei bei Verkauf).

    Einzelaktien (nicht Fonds), die vor dem 01.01.2009 erworben wurden,
    sind bei Verkauf komplett steuerfrei (Bestandsschutz Abgeltungsteuer).
    """
    return kaufdatum < BESTANDSSCHUTZ_STICHTAG and not is_fond
