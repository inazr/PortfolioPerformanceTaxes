"""Sparerpauschbetrag-Optimierung."""

from decimal import Decimal, ROUND_HALF_UP

from pptax.models.portfolio import Security
from pptax.models.tax import FreibetragOptimierungErgebnis, VerkaufsVorschlag
from pptax.engine.fifo import FifoBestand
from pptax.engine.tax_params import get_param

TWO_PLACES = Decimal("0.01")


def optimiere_freibetrag(
    jahr: int,
    veranlagungstyp: str,
    bereits_genutzt: Decimal,
    positionen: dict[str, FifoBestand],
    aktuelle_kurse: dict[str, Decimal],
    securities: dict[str, Security],
) -> FreibetragOptimierungErgebnis:
    """Berechne optimale Verkäufe um den Sparerpauschbetrag auszunutzen."""
    spb = get_param("sparerpauschbetrag", jahr)
    freibetrag_gesamt = Decimal(str(spb[veranlagungstyp]))
    freibetrag_verbleibend = max(Decimal("0"), freibetrag_gesamt - bereits_genutzt)

    if freibetrag_verbleibend <= 0:
        return FreibetragOptimierungErgebnis(
            jahr=jahr,
            freibetrag_gesamt=freibetrag_gesamt,
            freibetrag_bereits_genutzt=bereits_genutzt,
            freibetrag_verbleibend=Decimal("0"),
        )

    # Sammle Lots mit positivem steuerpflichtigem Gewinn pro Stück
    # Tuple: (uuid, lot_index, gewinn_stpfl_pro_stueck)
    kandidaten: list[tuple[str, int, Decimal]] = []
    for uuid, fifo in positionen.items():
        if uuid not in aktuelle_kurse or fifo.gesamtstuecke() <= 0:
            continue
        sec = securities.get(uuid)
        if sec is None:
            continue
        kurs = aktuelle_kurse[uuid]
        tfs_data = get_param("teilfreistellung", jahr)
        tfs = Decimal(str(tfs_data[sec.fonds_typ.value]))

        for lot_idx, lot in enumerate(fifo.bestand()):
            gewinn_pro_stueck_brutto = kurs - lot.einstandskurs
            vp_pro_stueck = (
                lot.vorabpauschalen_kumuliert / lot.stuecke
                if lot.stuecke > 0
                else Decimal("0")
            )
            gewinn_steuerlich = gewinn_pro_stueck_brutto - vp_pro_stueck
            gewinn_stpfl_pro_stueck = gewinn_steuerlich * (1 - tfs)

            if gewinn_stpfl_pro_stueck > 0:
                kandidaten.append((uuid, lot_idx, gewinn_stpfl_pro_stueck))

    # Sortiere: höchster steuerpflichtiger Gewinn pro Stück zuerst
    kandidaten.sort(key=lambda x: x[2], reverse=True)

    empfehlungen: list[VerkaufsVorschlag] = []
    noch_frei = freibetrag_verbleibend

    for uuid, lot_idx, gewinn_stpfl_pro_stueck in kandidaten:
        if noch_frei <= 0:
            break

        fifo = positionen[uuid]
        sec = securities[uuid]
        kurs = aktuelle_kurse[uuid]
        tfs_data = get_param("teilfreistellung", jahr)
        tfs = Decimal(str(tfs_data[sec.fonds_typ.value]))

        lot = fifo.bestand()[lot_idx]

        # Berechne benötigte Stücke aus diesem Lot
        stuecke_benoetigt = (noch_frei / gewinn_stpfl_pro_stueck).quantize(
            Decimal("0.00000001"), ROUND_HALF_UP
        )
        stuecke = min(stuecke_benoetigt, lot.stuecke)

        # Lot-weise Gewinnberechnung
        gewinn_pro_stueck_brutto = kurs - lot.einstandskurs
        vp_pro_stueck = (
            lot.vorabpauschalen_kumuliert / lot.stuecke
            if lot.stuecke > 0
            else Decimal("0")
        )
        gewinn_steuerlich = gewinn_pro_stueck_brutto - vp_pro_stueck
        gewinn_brutto = (stuecke * gewinn_steuerlich).quantize(
            TWO_PLACES, ROUND_HALF_UP
        )
        gewinn_stpfl = (stuecke * gewinn_stpfl_pro_stueck).quantize(
            TWO_PLACES, ROUND_HALF_UP
        )

        vorschlag = VerkaufsVorschlag(
            security_uuid=uuid,
            security_name=sec.name,
            isin=sec.isin,
            stuecke=stuecke,
            kaufdatum=lot.kaufdatum,
            einstandskurs=lot.einstandskurs,
            aktueller_kurs=kurs,
            brutto_erloes=(stuecke * kurs).quantize(TWO_PLACES, ROUND_HALF_UP),
            gewinn_brutto=gewinn_brutto,
            teilfreistellung_satz=tfs,
            gewinn_steuerpflichtig=gewinn_stpfl,
            steuer=Decimal("0"),  # Innerhalb Freibetrag = keine Steuer
            netto_erloes=(stuecke * kurs).quantize(TWO_PLACES, ROUND_HALF_UP),
        )
        empfehlungen.append(vorschlag)
        noch_frei -= gewinn_stpfl

    return FreibetragOptimierungErgebnis(
        jahr=jahr,
        freibetrag_gesamt=freibetrag_gesamt,
        freibetrag_bereits_genutzt=bereits_genutzt,
        freibetrag_verbleibend=freibetrag_verbleibend,
        verkaufsempfehlungen=empfehlungen,
    )
