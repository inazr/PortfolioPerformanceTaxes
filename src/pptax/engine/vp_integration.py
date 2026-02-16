"""Integration der Vorabpauschale in FIFO-Bestände.

Berechnet pro Lot die kumulierte Vorabpauschale für alle abgeschlossenen
Jahre vor dem Verkaufsjahr (§ 19 Abs. 1 Satz 3 InvStG).
"""

from collections import defaultdict
from decimal import Decimal

from pptax.engine.fifo import FifoBestand
from pptax.engine.kurs_utils import find_nearest_kurs
from pptax.engine.tax_params import get_param
from pptax.engine.vorabpauschale import berechne_vorabpauschale
from pptax.models.portfolio import Security, Transaction, TransaktionsTyp

from datetime import date


def apply_vorabpauschalen(
    positionen: dict[str, FifoBestand],
    securities: dict[str, Security],
    kurse_map: dict[str, dict[str, Decimal]],
    transactions: list[Transaction],
    steuerjahr: int,
) -> None:
    """Berechne und verteile Vorabpauschalen auf alle FIFO-Lots.

    Für jedes Lot wird die VP für jedes abgeschlossene Jahr von
    lot.kaufdatum.year bis steuerjahr-1 berechnet und auf das Lot addiert.

    Args:
        positionen: FIFO-Bestände pro Security
        securities: Security-Objekte nach UUID
        kurse_map: Verschachtelte Map security_uuid -> datum_iso -> kurs
        transactions: Alle Transaktionen (für Dividenden)
        steuerjahr: Das Verkaufs-/Steuerjahr (VP nur bis steuerjahr-1)
    """
    # Dividenden pro Security und Jahr sammeln
    dividenden: dict[str, dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for tx in transactions:
        if tx.typ == TransaktionsTyp.DIVIDENDE:
            dividenden[tx.security_uuid][tx.datum.year] += tx.gesamtbetrag

    for sec_uuid, fifo in positionen.items():
        sec = securities.get(sec_uuid)
        if sec is None:
            continue

        sec_kurse = kurse_map.get(sec_uuid, {})
        sec_dividenden = dividenden.get(sec_uuid, {})

        lots = fifo.bestand()
        # Gesamtstücke pro Jahr für anteilige Dividenden-Verteilung
        # (wird pro Lot berechnet: lot.stuecke / gesamt_stuecke)
        gesamt_stuecke = fifo.gesamtstuecke()
        if gesamt_stuecke == 0:
            continue

        for lot_idx, lot in enumerate(lots):
            start_year = lot.kaufdatum.year
            end_year = steuerjahr - 1  # nur abgeschlossene Jahre

            for jahr in range(start_year, end_year + 1):
                # Basiszins prüfen
                try:
                    basiszins = get_param("basiszins_vorabpauschale", jahr)
                except ValueError:
                    continue
                if basiszins < 0:
                    continue

                # Kurse am Jahresanfang und -ende suchen
                kurs_jan1 = find_nearest_kurs(sec_kurse, date(jahr, 1, 1))
                kurs_dec31 = find_nearest_kurs(sec_kurse, date(jahr, 12, 31))
                if kurs_jan1 is None or kurs_dec31 is None:
                    continue

                wert_anfang = kurs_jan1 * lot.stuecke
                wert_ende = kurs_dec31 * lot.stuecke

                # Dividenden anteilig nach Stückzahl des Lots
                jahr_div_gesamt = sec_dividenden.get(jahr, Decimal("0"))
                if gesamt_stuecke > 0:
                    ausschuettungen = jahr_div_gesamt * lot.stuecke / gesamt_stuecke
                else:
                    ausschuettungen = Decimal("0")

                # Kaufdatum nur übergeben wenn unterjähriger Kauf
                kaufdatum = lot.kaufdatum if lot.kaufdatum.year == jahr else None

                try:
                    erg = berechne_vorabpauschale(
                        security=sec,
                        jahr=jahr,
                        wert_anfang=wert_anfang,
                        wert_ende=wert_ende,
                        ausschuettungen=ausschuettungen,
                        kaufdatum=kaufdatum,
                    )
                except ValueError:
                    continue

                if erg.vorabpauschale_brutto > 0:
                    fifo.add_vorabpauschale_to_lot(lot_idx, erg.vorabpauschale_brutto)
