"""Netto-Verkaufsplanung."""

import copy
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

from pptax.models.portfolio import Security
from pptax.models.tax import NettoBetragPlan, VerkaufsVorschlag
from pptax.engine.fifo import FifoBestand
from pptax.engine.tax_params import get_param, get_gesamtsteuersatz

TWO_PLACES = Decimal("0.01")


def plane_netto_verkauf(
    ziel_netto: Decimal,
    jahr: int,
    veranlagungstyp: str,
    freibetrag_genutzt: Decimal,
    positionen: dict[str, FifoBestand],
    aktuelle_kurse: dict[str, Decimal],
    securities: dict[str, Security],
    kirchensteuer: bool = False,
    bundesland: str = "default",
) -> NettoBetragPlan:
    """Berechne Verkaufsplan um einen Netto-Zielbetrag zu erhalten."""
    steuersatz = get_gesamtsteuersatz(jahr, kirchensteuer, bundesland)
    spb = get_param("sparerpauschbetrag", jahr)
    freibetrag_gesamt = Decimal(str(spb[veranlagungstyp]))
    freibetrag_verbleibend = max(Decimal("0"), freibetrag_gesamt - freibetrag_genutzt)

    verkaufsplan: list[VerkaufsVorschlag] = []
    noch_benoetigtes_netto = ziel_netto
    brutto_gesamt = Decimal("0")
    steuer_gesamt = Decimal("0")
    freibetrag_in_verkauf_genutzt = Decimal("0")

    # Iteriere über alle Positionen
    for uuid in sorted(positionen.keys()):
        if noch_benoetigtes_netto <= 0:
            break

        fifo = positionen[uuid]
        if fifo.gesamtstuecke() <= 0 or uuid not in aktuelle_kurse:
            continue

        sec = securities.get(uuid)
        if sec is None:
            continue

        kurs = aktuelle_kurse[uuid]
        tfs_data = get_param("teilfreistellung", jahr)
        tfs = Decimal(str(tfs_data[sec.fonds_typ.value]))

        # Simuliere lotweise
        sim_fifo = FifoBestand(sec.uuid)
        sim_fifo._lots = copy.deepcopy(fifo._lots)

        for lot in fifo.bestand():
            if noch_benoetigtes_netto <= 0:
                break

            gewinn_pro_stueck_brutto = kurs - lot.einstandskurs
            vp_pro_stueck = lot.vorabpauschalen_kumuliert / lot.stuecke if lot.stuecke > 0 else Decimal("0")
            gewinn_steuerlich = gewinn_pro_stueck_brutto - vp_pro_stueck
            gewinn_stpfl_pro_stueck = (gewinn_steuerlich * (1 - tfs))

            # Steuer pro Stück berechnen unter Berücksichtigung des Freibetrags
            if gewinn_stpfl_pro_stueck > 0 and freibetrag_verbleibend > 0:
                # Berechne wie viele Stücke komplett freibetragsfrei sind
                stuecke_frei = min(
                    lot.stuecke,
                    (freibetrag_verbleibend / gewinn_stpfl_pro_stueck).quantize(
                        Decimal("0.00000001"), ROUND_HALF_UP
                    ),
                )
            else:
                stuecke_frei = Decimal("0")

            # Berechne benötigte Stücke
            # Netto pro Stück: bei freibetragsfreien = kurs, sonst = kurs - steuer
            if gewinn_stpfl_pro_stueck > 0:
                steuer_pro_stueck = (gewinn_stpfl_pro_stueck * steuersatz).quantize(
                    TWO_PLACES, ROUND_HALF_UP
                )
            else:
                steuer_pro_stueck = Decimal("0")

            netto_pro_stueck_frei = kurs
            netto_pro_stueck_besteuert = kurs - steuer_pro_stueck

            # Zuerst freibetragsfreie Stücke nutzen
            stuecke_gesamt = Decimal("0")
            lot_steuer = Decimal("0")

            if stuecke_frei > 0 and noch_benoetigtes_netto > 0:
                n_frei = min(
                    stuecke_frei,
                    (noch_benoetigtes_netto / netto_pro_stueck_frei).quantize(
                        Decimal("0.00000001"), ROUND_UP
                    ),
                )
                n_frei = min(n_frei, lot.stuecke)
                stuecke_gesamt += n_frei
                netto_frei = (n_frei * netto_pro_stueck_frei).quantize(TWO_PLACES, ROUND_HALF_UP)
                noch_benoetigtes_netto -= netto_frei
                freibetrag_verbleibend -= (n_frei * gewinn_stpfl_pro_stueck).quantize(TWO_PLACES, ROUND_HALF_UP)
                freibetrag_in_verkauf_genutzt += (n_frei * gewinn_stpfl_pro_stueck).quantize(TWO_PLACES, ROUND_HALF_UP)

            verbleibend_im_lot = lot.stuecke - stuecke_gesamt
            if noch_benoetigtes_netto > 0 and verbleibend_im_lot > 0:
                if netto_pro_stueck_besteuert > 0:
                    n_besteuert = min(
                        verbleibend_im_lot,
                        (noch_benoetigtes_netto / netto_pro_stueck_besteuert).quantize(
                            Decimal("0.00000001"), ROUND_UP
                        ),
                    )
                else:
                    n_besteuert = verbleibend_im_lot
                n_besteuert = min(n_besteuert, verbleibend_im_lot)
                stuecke_gesamt += n_besteuert
                lot_steuer = (n_besteuert * steuer_pro_stueck).quantize(TWO_PLACES, ROUND_HALF_UP)
                netto_besteuert = (n_besteuert * kurs - lot_steuer).quantize(TWO_PLACES, ROUND_HALF_UP)
                noch_benoetigtes_netto -= netto_besteuert

            if stuecke_gesamt > 0:
                brutto = (stuecke_gesamt * kurs).quantize(TWO_PLACES, ROUND_HALF_UP)
                gewinn = (stuecke_gesamt * gewinn_pro_stueck_brutto).quantize(TWO_PLACES, ROUND_HALF_UP)
                gewinn_stpfl = (stuecke_gesamt * gewinn_stpfl_pro_stueck).quantize(TWO_PLACES, ROUND_HALF_UP)

                vorschlag = VerkaufsVorschlag(
                    security_uuid=uuid,
                    security_name=sec.name,
                    isin=sec.isin,
                    stuecke=stuecke_gesamt,
                    kaufdatum=lot.kaufdatum,
                    einstandskurs=lot.einstandskurs,
                    aktueller_kurs=kurs,
                    brutto_erloes=brutto,
                    gewinn_brutto=gewinn,
                    teilfreistellung_satz=tfs,
                    gewinn_steuerpflichtig=gewinn_stpfl,
                    steuer=lot_steuer,
                    netto_erloes=(brutto - lot_steuer).quantize(TWO_PLACES, ROUND_HALF_UP),
                )
                verkaufsplan.append(vorschlag)
                brutto_gesamt += brutto
                steuer_gesamt += lot_steuer

    erreichtes_netto = (brutto_gesamt - steuer_gesamt).quantize(TWO_PLACES, ROUND_HALF_UP)

    return NettoBetragPlan(
        ziel_netto=ziel_netto,
        erreichtes_netto=erreichtes_netto,
        brutto_gesamt=brutto_gesamt,
        steuer_gesamt=steuer_gesamt,
        freibetrag_genutzt=freibetrag_in_verkauf_genutzt,
        verkaufsplan=verkaufsplan,
    )


def pruefe_erreichbarkeit(
    ziel_netto: Decimal,
    positionen: dict[str, FifoBestand],
    aktuelle_kurse: dict[str, Decimal],
) -> bool:
    """Prüfe ob der Zielbetrag mit den vorhandenen Beständen erreichbar ist."""
    gesamt_wert = Decimal("0")
    for uuid, fifo in positionen.items():
        if uuid in aktuelle_kurse:
            gesamt_wert += fifo.gesamtstuecke() * aktuelle_kurse[uuid]
    return gesamt_wert >= ziel_netto
