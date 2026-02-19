"""Tests für Depot-Filter-Logik."""

from datetime import date
from decimal import Decimal

from pptax.models.portfolio import (
    Security,
    Transaction,
    TransaktionsTyp,
    HistorischerKurs,
    PortfolioInfo,
    PortfolioData,
)


def _make_test_data() -> PortfolioData:
    """Erstelle Test-PortfolioData mit zwei Depots."""
    return PortfolioData(
        securities=[
            Security(uuid="sec-001", name="ETF A"),
            Security(uuid="sec-002", name="ETF B"),
        ],
        transactions=[
            Transaction(
                datum=date(2023, 1, 15),
                typ=TransaktionsTyp.KAUF,
                security_uuid="sec-001",
                stuecke=Decimal("100"),
                kurs=Decimal("50"),
                gesamtbetrag=Decimal("5000"),
                portfolio_uuid="ptf-001",
            ),
            Transaction(
                datum=date(2023, 6, 1),
                typ=TransaktionsTyp.KAUF,
                security_uuid="sec-002",
                stuecke=Decimal("50"),
                kurs=Decimal("80"),
                gesamtbetrag=Decimal("4000"),
                portfolio_uuid="ptf-002",
            ),
            Transaction(
                datum=date(2023, 9, 1),
                typ=TransaktionsTyp.DIVIDENDE,
                security_uuid="sec-001",
                stuecke=Decimal("100"),
                kurs=Decimal("0"),
                gesamtbetrag=Decimal("200"),
                portfolio_uuid=None,  # Transaktion ohne Depot-Zuordnung
            ),
        ],
        kurse=[
            HistorischerKurs(
                security_uuid="sec-001", datum=date(2023, 12, 31), kurs=Decimal("55")
            ),
        ],
        portfolios=[
            PortfolioInfo(uuid="ptf-001", name="Depot A", reference_account_uuid="acc-001"),
            PortfolioInfo(uuid="ptf-002", name="Depot B", reference_account_uuid="acc-002"),
        ],
    )


def _filter_by_depots(
    data: PortfolioData, selected_uuids: set[str]
) -> PortfolioData:
    """Filtert PortfolioData nach ausgewählten Depots (gleiche Logik wie GUI)."""
    filtered_tx = [
        tx
        for tx in data.transactions
        if tx.portfolio_uuid is None or tx.portfolio_uuid in selected_uuids
    ]
    return PortfolioData(
        securities=data.securities,
        transactions=filtered_tx,
        kurse=data.kurse,
        portfolios=data.portfolios,
    )


class TestDepotFilter:
    def test_filter_single_depot(self):
        """Nur Transaktionen eines Depots werden eingeschlossen."""
        data = _make_test_data()
        filtered = _filter_by_depots(data, {"ptf-001"})

        # ptf-001 tx + None tx
        assert len(filtered.transactions) == 2
        uuids = {tx.portfolio_uuid for tx in filtered.transactions}
        assert uuids == {"ptf-001", None}

    def test_filter_other_depot(self):
        """Filter auf anderes Depot."""
        data = _make_test_data()
        filtered = _filter_by_depots(data, {"ptf-002"})

        assert len(filtered.transactions) == 2
        uuids = {tx.portfolio_uuid for tx in filtered.transactions}
        assert uuids == {"ptf-002", None}

    def test_none_portfolio_always_included(self):
        """Transaktionen ohne portfolio_uuid sind immer enthalten."""
        data = _make_test_data()

        # Auch bei leerem Filter enthält man die None-Transaktion
        filtered = _filter_by_depots(data, set())
        assert len(filtered.transactions) == 1
        assert filtered.transactions[0].portfolio_uuid is None

    def test_all_depots_selected(self):
        """Alle Depots ausgewählt = alle Transaktionen."""
        data = _make_test_data()
        filtered = _filter_by_depots(data, {"ptf-001", "ptf-002"})
        assert len(filtered.transactions) == 3

    def test_securities_and_kurse_shared(self):
        """Securities und Kurse werden nicht gefiltert, nur Transaktionen."""
        data = _make_test_data()
        filtered = _filter_by_depots(data, {"ptf-001"})

        assert filtered.securities is data.securities
        assert filtered.kurse is data.kurse
        assert filtered.portfolios is data.portfolios
