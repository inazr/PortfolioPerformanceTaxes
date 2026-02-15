"""Tests für PP XML Parser."""

from pathlib import Path
from decimal import Decimal

import pytest

from pptax.parser.pp_xml_parser import parse_portfolio_file
from pptax.models.portfolio import TransaktionsTyp

SAMPLE_XML = Path(__file__).parent / "test_data" / "sample_portfolio.xml"


class TestPPXMLParser:
    def test_parse_securities(self):
        """Parse Wertpapiere aus Sample-XML."""
        data = parse_portfolio_file(SAMPLE_XML)
        assert len(data.securities) == 3

        names = {s.name for s in data.securities}
        assert "Vanguard FTSE All-World UCITS ETF" in names

        # Prüfe ISIN
        world_etf = next(s for s in data.securities if "Vanguard" in s.name)
        assert world_etf.isin == "IE00BK5BQT80"
        assert world_etf.uuid == "sec-etf-world-001"

    def test_parse_transactions(self):
        """Parse Transaktionen."""
        data = parse_portfolio_file(SAMPLE_XML)
        assert len(data.transactions) > 0

        # Käufe und Verkäufe
        kaeufe = [t for t in data.transactions if t.typ == TransaktionsTyp.KAUF]
        verkaeufe = [t for t in data.transactions if t.typ == TransaktionsTyp.VERKAUF]
        dividenden = [t for t in data.transactions if t.typ == TransaktionsTyp.DIVIDENDE]

        assert len(kaeufe) >= 3  # 3 Käufe im XML
        assert len(verkaeufe) >= 1  # 1 Verkauf
        assert len(dividenden) >= 1  # Dividenden

    def test_amount_conversion(self):
        """PP-Integer-Beträge werden korrekt konvertiert."""
        data = parse_portfolio_file(SAMPLE_XML)
        # Erster Kauf: amount=950000 -> 9500.00
        kaeufe = sorted(
            [t for t in data.transactions if t.typ == TransaktionsTyp.KAUF],
            key=lambda t: t.datum,
        )
        first_buy = kaeufe[0]
        assert first_buy.gesamtbetrag == Decimal("9500.00")
        # shares=10000000000 -> 100
        assert first_buy.stuecke == Decimal("100")

    def test_parse_kurse(self):
        """Parse historische Kurse."""
        data = parse_portfolio_file(SAMPLE_XML)
        assert len(data.kurse) > 0

        # Prüfe einen bekannten Kurs: sec-etf-world-001, 2023-01-01, v=9500 -> 95.00
        from datetime import date
        matching = [
            k for k in data.kurse
            if k.security_uuid == "sec-etf-world-001"
            and k.datum == date(2023, 1, 1)
        ]
        assert len(matching) == 1
        assert matching[0].kurs == Decimal("95.00")


class TestPPXMLParserEdgeCases:
    def test_nonexistent_file_raises(self):
        with pytest.raises(Exception):
            parse_portfolio_file("/nonexistent/file.xml")
