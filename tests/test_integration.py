"""Integration test: XML parse -> FIFO -> Vorabpauschale -> Freibetrag -> Verkauf."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from pptax.parser.pp_xml_parser import parse_portfolio_file
from pptax.models.portfolio import TransaktionsTyp, FondsTyp
from pptax.engine.fifo import FifoBestand
from pptax.engine.vorabpauschale import berechne_vorabpauschale
from pptax.engine.freibetrag import optimiere_freibetrag
from pptax.engine.verkauf import plane_netto_verkauf

SAMPLE_XML = Path(__file__).parent / "test_data" / "sample_portfolio.xml"


class TestIntegration:
    def test_full_pipeline(self):
        """End-to-end: Parse -> FIFO -> Vorabpauschale -> Freibetrag -> Verkauf."""
        # 1. Parse
        data = parse_portfolio_file(SAMPLE_XML)
        assert len(data.securities) == 3

        # 2. Build FIFO
        positionen: dict[str, FifoBestand] = {}
        sorted_tx = sorted(data.transactions, key=lambda t: t.datum)
        for tx in sorted_tx:
            if tx.typ in (TransaktionsTyp.KAUF, TransaktionsTyp.EINLIEFERUNG):
                if tx.security_uuid not in positionen:
                    positionen[tx.security_uuid] = FifoBestand(tx.security_uuid)
                positionen[tx.security_uuid].kauf(tx.datum, tx.stuecke, tx.kurs)
            elif tx.typ in (TransaktionsTyp.VERKAUF, TransaktionsTyp.AUSLIEFERUNG):
                if tx.security_uuid in positionen:
                    positionen[tx.security_uuid].verkauf(tx.datum, tx.stuecke, tx.kurs)

        # World ETF: 100 bought, then 20 bought, then 30 sold = 90 remaining
        assert positionen["sec-etf-world-001"].gesamtstuecke() == Decimal("90")
        # Bond ETF: 50 bought, no sales = 50
        assert positionen["sec-bond-etf-002"].gesamtstuecke() == Decimal("50")
        # Immo ETF: 200 bought, no sales = 200
        assert positionen["sec-immo-003"].gesamtstuecke() == Decimal("200")

        # 3. Vorabpauschale
        world_sec = next(s for s in data.securities if s.uuid == "sec-etf-world-001")
        erg = berechne_vorabpauschale(
            world_sec, 2023,
            wert_anfang=Decimal("95.00"),  # from prices
            wert_ende=Decimal("112.00"),
        )
        assert erg.steuer >= Decimal("0")

        # 4. Freibetrag
        aktuelle_kurse = {
            "sec-etf-world-001": Decimal("135.00"),
            "sec-bond-etf-002": Decimal("118.00"),
            "sec-immo-003": Decimal("28.00"),
        }
        sec_map = {s.uuid: s for s in data.securities}

        fb_result = optimiere_freibetrag(
            jahr=2023,
            veranlagungstyp="single",
            bereits_genutzt=Decimal("0"),
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=sec_map,
        )
        assert fb_result.freibetrag_gesamt == Decimal("1000")

        # 5. Verkaufsplanung
        plan = plane_netto_verkauf(
            ziel_netto=Decimal("1000"),
            jahr=2023,
            veranlagungstyp="single",
            freibetrag_genutzt=Decimal("0"),
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=sec_map,
        )
        assert plan.erreichtes_netto > Decimal("0")
        assert plan.brutto_gesamt >= plan.erreichtes_netto

    def test_verification_case(self):
        """Spec verification: 2023, 10.000€ -> 12.000€, Aktienfonds -> 32,96€."""
        from pptax.models.portfolio import Security
        sec = Security(uuid="v", name="V", fonds_typ=FondsTyp.AKTIENFONDS)
        erg = berechne_vorabpauschale(sec, 2023, Decimal("10000"), Decimal("12000"))
        assert erg.steuer == Decimal("32.96")
