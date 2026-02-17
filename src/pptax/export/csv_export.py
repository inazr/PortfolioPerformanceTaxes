"""CSV Export der Berechnungsergebnisse."""

import csv
import io
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from pptax.models.tax import (
    VorabpauschaleErgebnis,
    FreibetragOptimierungErgebnis,
    NettoBetragPlan,
    VerkaufsVorschlag,
)

BOM = "\ufeff"


def _format_decimal(value: Decimal, german: bool = True) -> str:
    """Formatiere Decimal für CSV."""
    s = f"{value:.2f}"
    if german:
        s = s.replace(".", ",")
    return s


def _format_percent(value: Decimal, german: bool = True) -> str:
    """Formatiere Prozentwert für CSV."""
    s = f"{value * 100:.2f}"
    if german:
        s = s.replace(".", ",")
    return s + " %"


def export_vorabpauschale(
    ergebnisse: list[VorabpauschaleErgebnis],
    securities: dict[str, "Security"],
    filepath: str | Path,
    german_format: bool = True,
) -> None:
    """Exportiere Vorabpauschale-Ergebnisse als CSV."""
    filepath = Path(filepath)
    header = [
        "Wertpapier",
        "ISIN",
        "Jahr",
        "Wert 01.01.",
        "Wert 31.12.",
        "Basiszins",
        "Basisertrag",
        "Wertsteigerung",
        "Ausschüttungen",
        "Vorabpauschale brutto",
        "Teilfreistellung",
        "Steuerpflichtig",
        "Steuer",
    ]

    rows = []
    for e in ergebnisse:
        sec = securities.get(e.security_uuid)
        name = sec.name if sec else e.security_uuid
        isin = sec.isin if sec else ""
        rows.append([
            name,
            isin or "",
            str(e.jahr),
            _format_decimal(e.wert_jahresanfang, german_format),
            _format_decimal(e.wert_jahresende, german_format),
            _format_percent(e.basiszins, german_format),
            _format_decimal(e.basisertrag, german_format),
            _format_decimal(e.wertsteigerung, german_format),
            _format_decimal(e.ausschuettungen, german_format),
            _format_decimal(e.vorabpauschale_brutto, german_format),
            _format_percent(e.teilfreistellung_satz, german_format),
            _format_decimal(e.vorabpauschale_steuerpflichtig, german_format),
            _format_decimal(e.steuer, german_format),
        ])

    _write_csv(filepath, header, rows, german_format)


def export_freibetrag(
    ergebnis: FreibetragOptimierungErgebnis,
    filepath: str | Path,
    german_format: bool = True,
) -> None:
    """Exportiere Freibetrag-Optimierung als CSV."""
    filepath = Path(filepath)
    header = [
        "Wertpapier",
        "ISIN",
        "Stücke",
        "Kaufdatum",
        "Einstandskurs",
        "Aktueller Kurs",
        "Brutto-Erlös",
        "Gewinn brutto",
        "Gewinn steuerpflichtig",
        "Steuer",
        "Netto-Erlös",
    ]

    # Gruppiere nach Security für Summary-Zeilen
    grouped: dict[str, list[VerkaufsVorschlag]] = defaultdict(list)
    order: list[str] = []
    for v in ergebnis.verkaufsempfehlungen:
        if v.security_uuid not in grouped:
            order.append(v.security_uuid)
        grouped[v.security_uuid].append(v)

    rows = []
    for uuid in order:
        lots = grouped[uuid]
        if len(lots) > 1:
            # Summary-Zeile
            first = lots[0]
            total_stuecke = sum(v.stuecke for v in lots)
            avg_einstand = (
                sum(v.einstandskurs * v.stuecke for v in lots) / total_stuecke
                if total_stuecke > 0
                else Decimal("0")
            )
            rows.append([
                f"{first.security_name} (Gesamt)",
                first.isin or "",
                _format_decimal(total_stuecke, german_format),
                "",
                _format_decimal(avg_einstand, german_format),
                _format_decimal(first.aktueller_kurs, german_format),
                _format_decimal(sum(v.brutto_erloes for v in lots), german_format),
                _format_decimal(sum(v.gewinn_brutto for v in lots), german_format),
                _format_decimal(sum(v.gewinn_steuerpflichtig for v in lots), german_format),
                _format_decimal(sum(v.steuer for v in lots), german_format),
                _format_decimal(sum(v.netto_erloes for v in lots), german_format),
            ])
        for v in lots:
            rows.append(_vorschlag_to_row(v, german_format))

    _write_csv(filepath, header, rows, german_format)


def export_verkaufsplan(
    plan: NettoBetragPlan,
    filepath: str | Path,
    german_format: bool = True,
) -> None:
    """Exportiere Verkaufsplan als CSV."""
    filepath = Path(filepath)
    header = [
        "Wertpapier",
        "ISIN",
        "Stücke",
        "Kaufdatum",
        "Einstandskurs",
        "Aktueller Kurs",
        "Brutto-Erlös",
        "Gewinn brutto",
        "Gewinn steuerpflichtig",
        "Steuer",
        "Netto-Erlös",
    ]

    rows = []
    for v in plan.verkaufsplan:
        rows.append(_vorschlag_to_row(v, german_format))

    _write_csv(filepath, header, rows, german_format)


def _vorschlag_to_row(v: VerkaufsVorschlag, german: bool) -> list[str]:
    kaufdatum_str = v.kaufdatum.strftime("%d.%m.%Y") if v.kaufdatum else ""
    return [
        v.security_name,
        v.isin or "",
        _format_decimal(v.stuecke, german),
        kaufdatum_str,
        _format_decimal(v.einstandskurs, german),
        _format_decimal(v.aktueller_kurs, german),
        _format_decimal(v.brutto_erloes, german),
        _format_decimal(v.gewinn_brutto, german),
        _format_decimal(v.gewinn_steuerpflichtig, german),
        _format_decimal(v.steuer, german),
        _format_decimal(v.netto_erloes, german),
    ]


def _write_csv(
    filepath: Path,
    header: list[str],
    rows: list[list[str]],
    german_format: bool,
) -> None:
    """Schreibe CSV-Datei mit UTF-8 BOM für Excel-Kompatibilität."""
    delimiter = ";" if german_format else ","
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(header)
        writer.writerows(rows)
