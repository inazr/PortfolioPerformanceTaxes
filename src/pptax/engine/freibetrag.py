"""Sparerpauschbetrag-Optimierung."""

from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from math import ceil

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

    # Sammle Positionen mit positivem Gewinn pro Stück
    kandidaten: list[tuple[str, Decimal]] = []  # (uuid, gewinn_pro_stueck_steuerpflichtig)
    for uuid, fifo in positionen.items():
        if uuid not in aktuelle_kurse or fifo.gesamtstuecke() <= 0:
            continue
        sec = securities.get(uuid)
        if sec is None:
            continue
        kurs = aktuelle_kurse[uuid]
        tfs_data = get_param("teilfreistellung", jahr)
        tfs = Decimal(str(tfs_data[sec.fonds_typ.value]))

        # Simuliere Verkauf von 1 Stück
        stuecke_gesamt = fifo.gesamtstuecke()
        gewinn_brutto = fifo.gewinn_bei_verkauf(stuecke_gesamt, kurs)
        if gewinn_brutto <= 0:
            continue

        gewinn_stpfl_pro_stueck = (gewinn_brutto / stuecke_gesamt * (1 - tfs))
        kandidaten.append((uuid, gewinn_stpfl_pro_stueck))

    # Sortiere: höchster steuerpflichtiger Gewinn pro Stück zuerst
    kandidaten.sort(key=lambda x: x[1], reverse=True)

    empfehlungen: list[VerkaufsVorschlag] = []
    noch_frei = freibetrag_verbleibend

    for uuid, gewinn_stpfl_pro_stueck in kandidaten:
        if noch_frei <= 0:
            break

        fifo = positionen[uuid]
        sec = securities[uuid]
        kurs = aktuelle_kurse[uuid]
        tfs_data = get_param("teilfreistellung", jahr)
        tfs = Decimal(str(tfs_data[sec.fonds_typ.value]))

        # Berechne benötigte Stücke
        stuecke_benoetigt = (noch_frei / gewinn_stpfl_pro_stueck).quantize(
            Decimal("0.00000001"), ROUND_HALF_UP
        )
        stuecke_verfuegbar = fifo.gesamtstuecke()
        stuecke = min(stuecke_benoetigt, stuecke_verfuegbar)

        # Simuliere den tatsächlichen Gewinn
        gewinn_brutto = fifo.gewinn_bei_verkauf(stuecke, kurs)
        gewinn_stpfl = (gewinn_brutto * (1 - tfs)).quantize(TWO_PLACES, ROUND_HALF_UP)

        lots = fifo.bestand()
        erstes_lot = lots[0] if lots else None

        vorschlag = VerkaufsVorschlag(
            security_uuid=uuid,
            security_name=sec.name,
            isin=sec.isin,
            stuecke=stuecke,
            kaufdatum=erstes_lot.kaufdatum if erstes_lot else None,
            einstandskurs=erstes_lot.einstandskurs if erstes_lot else Decimal("0"),
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
