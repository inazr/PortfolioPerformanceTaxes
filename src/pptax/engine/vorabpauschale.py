"""Vorabpauschale-Berechnung gem. § 18 InvStG."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from pptax.models.portfolio import Security, FondsTyp
from pptax.models.tax import VorabpauschaleErgebnis
from pptax.engine.tax_params import get_param, get_gesamtsteuersatz

TWO_PLACES = Decimal("0.01")


def berechne_vorabpauschale(
    security: Security,
    jahr: int,
    wert_anfang: Decimal,
    wert_ende: Decimal,
    ausschuettungen: Decimal = Decimal("0"),
    kaufdatum: date | None = None,
) -> VorabpauschaleErgebnis:
    """Berechne die Vorabpauschale für ein Wertpapier und ein Steuerjahr.

    Implementiert alle 8 Regeln aus der Spezifikation.
    """
    basiszins = Decimal(str(get_param("basiszins_vorabpauschale", jahr)))
    faktor = Decimal(str(get_param("vorabpauschale_faktor", jahr)))
    tfs_data = get_param("teilfreistellung", jahr)
    tfs = Decimal(str(tfs_data[security.fonds_typ.value]))

    # Regel: Negativer Basiszins -> Vorabpauschale = 0
    if basiszins < 0:
        return _zero_result(security.uuid, jahr, wert_anfang, wert_ende, basiszins, tfs, ausschuettungen)

    # 1. Basisertrag = Wert_1.Januar × Basiszins × 0,7
    basisertrag = (wert_anfang * basiszins * faktor).quantize(TWO_PLACES, ROUND_HALF_UP)

    # 2. Wertsteigerung
    wertsteigerung = wert_ende - wert_anfang

    # 3. Wenn Wertsteigerung <= 0: Vorabpauschale = 0
    if wertsteigerung <= 0:
        return _zero_result(security.uuid, jahr, wert_anfang, wert_ende, basiszins, tfs, ausschuettungen)

    # 4. Vorabpauschale_brutto = min(Basisertrag, Wertsteigerung)
    vp_brutto = min(basisertrag, wertsteigerung)

    # 5. Abzug Ausschüttungen
    vp_brutto -= ausschuettungen

    # 6. Nicht negativ
    vp_brutto = max(Decimal("0"), vp_brutto)

    # Unterjähriger Kauf: Vorabpauschale × (12 - volle_Monate_vor_Kauf) / 12
    if kaufdatum is not None and kaufdatum.year == jahr:
        volle_monate_vor_kauf = kaufdatum.month - 1
        faktor_unterjaehrig = Decimal(12 - volle_monate_vor_kauf) / Decimal(12)
        vp_brutto = (vp_brutto * faktor_unterjaehrig).quantize(TWO_PLACES, ROUND_HALF_UP)

    # 7. Steuerpflichtig = Vorabpauschale_brutto × (1 - Teilfreistellungssatz)
    vp_steuerpflichtig = (vp_brutto * (1 - tfs)).quantize(TWO_PLACES, ROUND_HALF_UP)

    # 8. Steuer = Steuerpflichtig × Gesamtsteuersatz
    steuersatz = get_gesamtsteuersatz(jahr)
    steuer = (vp_steuerpflichtig * steuersatz).quantize(TWO_PLACES, ROUND_HALF_UP)

    return VorabpauschaleErgebnis(
        security_uuid=security.uuid,
        jahr=jahr,
        wert_jahresanfang=wert_anfang,
        wert_jahresende=wert_ende,
        basiszins=basiszins,
        basisertrag=basisertrag,
        wertsteigerung=wertsteigerung,
        ausschuettungen=ausschuettungen,
        vorabpauschale_brutto=vp_brutto,
        teilfreistellung_satz=tfs,
        vorabpauschale_steuerpflichtig=vp_steuerpflichtig,
        steuer=steuer,
    )


def berechne_jahresuebersicht(
    securities: list[Security],
    jahr: int,
    werte_anfang: dict[str, Decimal],
    werte_ende: dict[str, Decimal],
    ausschuettungen: dict[str, Decimal] | None = None,
    kaufdaten: dict[str, date] | None = None,
) -> list[VorabpauschaleErgebnis]:
    """Berechne die Vorabpauschale für alle Wertpapiere eines Jahres."""
    if ausschuettungen is None:
        ausschuettungen = {}
    if kaufdaten is None:
        kaufdaten = {}

    ergebnisse = []
    for sec in securities:
        if sec.uuid not in werte_anfang or sec.uuid not in werte_ende:
            continue
        ergebnisse.append(
            berechne_vorabpauschale(
                security=sec,
                jahr=jahr,
                wert_anfang=werte_anfang[sec.uuid],
                wert_ende=werte_ende[sec.uuid],
                ausschuettungen=ausschuettungen.get(sec.uuid, Decimal("0")),
                kaufdatum=kaufdaten.get(sec.uuid),
            )
        )
    return ergebnisse


def _zero_result(
    security_uuid: str,
    jahr: int,
    wert_anfang: Decimal,
    wert_ende: Decimal,
    basiszins: Decimal,
    tfs: Decimal,
    ausschuettungen: Decimal,
) -> VorabpauschaleErgebnis:
    return VorabpauschaleErgebnis(
        security_uuid=security_uuid,
        jahr=jahr,
        wert_jahresanfang=wert_anfang,
        wert_jahresende=wert_ende,
        basiszins=basiszins,
        basisertrag=Decimal("0"),
        wertsteigerung=wert_ende - wert_anfang,
        ausschuettungen=ausschuettungen,
        vorabpauschale_brutto=Decimal("0"),
        teilfreistellung_satz=tfs,
        vorabpauschale_steuerpflichtig=Decimal("0"),
        steuer=Decimal("0"),
    )
