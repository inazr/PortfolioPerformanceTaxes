"""Shared pytest fixtures."""

from datetime import date
from decimal import Decimal

import pytest

from pptax.models.portfolio import (
    Security,
    Transaction,
    TransaktionsTyp,
    FifoPosition,
    FondsTyp,
    HistorischerKurs,
)


@pytest.fixture
def sample_security_aktien():
    return Security(
        uuid="sec-001",
        name="Test Aktienfonds ETF",
        isin="IE00TEST0001",
        fonds_typ=FondsTyp.AKTIENFONDS,
    )


@pytest.fixture
def sample_security_misch():
    return Security(
        uuid="sec-002",
        name="Test Mischfonds",
        isin="IE00TEST0002",
        fonds_typ=FondsTyp.MISCHFONDS,
    )


@pytest.fixture
def sample_security_sonstige():
    return Security(
        uuid="sec-003",
        name="Test Sonstige",
        isin="IE00TEST0003",
        fonds_typ=FondsTyp.SONSTIGE,
    )


@pytest.fixture
def sample_kauf_transaction():
    return Transaction(
        datum=date(2022, 3, 15),
        typ=TransaktionsTyp.KAUF,
        security_uuid="sec-001",
        stuecke=Decimal("100"),
        kurs=Decimal("95.00"),
        gesamtbetrag=Decimal("9500.00"),
        gebuehren=Decimal("15.00"),
    )


@pytest.fixture
def sample_fifo_position():
    return FifoPosition(
        kaufdatum=date(2022, 3, 15),
        stuecke=Decimal("100"),
        einstandskurs=Decimal("95.00"),
        security_uuid="sec-001",
    )
