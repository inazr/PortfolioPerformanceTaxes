"""Zentrale Lookup-Funktion für historische Steuerparameter."""

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

_DATA_FILE = Path(__file__).parent.parent / "data" / "tax_parameters.json"


@lru_cache(maxsize=1)
def _load_parameters() -> dict:
    """Lade tax_parameters.json (einmal, mit Caching)."""
    with open(_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_param(param_name: str, year: int):
    """Hole den gültigen Steuerparameter für ein gegebenes Jahr.

    Sucht den letzten Eintrag mit Jahreszahl <= year.
    Wirft ValueError wenn kein gültiger Eintrag existiert.
    """
    data = _load_parameters()
    if param_name not in data:
        raise ValueError(f"Unbekannter Parameter: {param_name}")

    param_data = data[param_name]
    # Filtere nur numerische Keys (Jahre), ignoriere _comment etc.
    year_keys = sorted(int(k) for k in param_data if k.isdigit())

    if not year_keys:
        raise ValueError(f"Keine Jahresdaten für Parameter: {param_name}")

    # Finde den letzten Key <= year
    valid_key = None
    for k in year_keys:
        if k <= year:
            valid_key = k
        else:
            break

    if valid_key is None:
        raise ValueError(
            f"Kein gültiger Eintrag für {param_name} im Jahr {year} "
            f"(frühester Eintrag: {year_keys[0]})"
        )

    return param_data[str(valid_key)]


def get_gesamtsteuersatz(
    year: int, kirchensteuer: bool = False, bundesland: str = "default"
) -> Decimal:
    """Berechne den kombinierten Steuersatz.

    Ohne Kirchensteuer: KESt + Soli = 0.25 + 0.25 * 0.055 = 0.26375
    Mit Kirchensteuer: Sonderberechnung gem. § 32d Abs. 1 Satz 3 EStG.
    """
    e = Decimal(str(get_param("abgeltungssteuer_satz", year)))
    s = Decimal(str(get_param("solidaritaetszuschlag_satz", year)))

    if not kirchensteuer:
        return e + e * s

    k_data = get_param("kirchensteuer_saetze", year)
    k = Decimal(str(k_data.get(bundesland, k_data["default"])))

    # KESt_effektiv = e / (1 + k * e) gem. § 32d Abs. 1 Satz 3 EStG
    kest_eff = e / (1 + k * e)
    soli = kest_eff * s
    kist = kest_eff * k
    return kest_eff + soli + kist
