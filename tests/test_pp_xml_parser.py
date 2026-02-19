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

        assert len(kaeufe) >= 4  # 4 Käufe im XML (3 Depot A + 1 Depot B)
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


class TestPortfolioExtraction:
    def test_parse_portfolios(self):
        """Parse Portfolio-Metadaten aus Sample-XML."""
        data = parse_portfolio_file(SAMPLE_XML)
        assert len(data.portfolios) == 2

        names = {p.name for p in data.portfolios}
        assert "Depot A" in names
        assert "Depot B" in names

    def test_portfolio_reference_account(self):
        """Portfolio referenceAccount UUID wird korrekt aufgelöst."""
        data = parse_portfolio_file(SAMPLE_XML)
        ptf_a = next(p for p in data.portfolios if p.uuid == "ptf-001")
        ptf_b = next(p for p in data.portfolios if p.uuid == "ptf-002")
        assert ptf_a.reference_account_uuid == "acc-001"
        assert ptf_b.reference_account_uuid == "acc-002"

    def test_transaction_portfolio_assignment(self):
        """Transaktionen werden ihrem Portfolio zugeordnet."""
        data = parse_portfolio_file(SAMPLE_XML)

        ptf_a_txs = [t for t in data.transactions if t.portfolio_uuid == "ptf-001"]
        ptf_b_txs = [t for t in data.transactions if t.portfolio_uuid == "ptf-002"]

        # Depot A: 4 Käufe + 1 Verkauf + 2 Dividenden = 7
        assert len(ptf_a_txs) == 7
        # Depot B: 1 Kauf + 1 Dividende = 2
        assert len(ptf_b_txs) == 2

    def test_dividend_account_mapping(self):
        """Dividenden werden über Account→Portfolio Mapping zugeordnet."""
        data = parse_portfolio_file(SAMPLE_XML)
        dividenden = [t for t in data.transactions if t.typ == TransaktionsTyp.DIVIDENDE]

        # Dividende in acc-001 → ptf-001
        div_a = [d for d in dividenden if d.portfolio_uuid == "ptf-001"]
        assert len(div_a) == 2

        # Dividende in acc-002 → ptf-002
        div_b = [d for d in dividenden if d.portfolio_uuid == "ptf-002"]
        assert len(div_b) == 1

    def test_no_duplicate_transactions(self):
        """Keine doppelten Transaktionen durch per-Portfolio + globale Iteration."""
        data = parse_portfolio_file(SAMPLE_XML)
        # 5 portfolio-tx (Depot A) + 1 portfolio-tx (Depot B) + 3 dividenden = 9
        assert len(data.transactions) == 9


class TestPPXMLParserEdgeCases:
    def test_nonexistent_file_raises(self):
        with pytest.raises(Exception):
            parse_portfolio_file("/nonexistent/file.xml")
