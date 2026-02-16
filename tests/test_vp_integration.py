"""Tests für Vorabpauschale-Integration in FIFO-Bestände."""

from datetime import date
from decimal import Decimal

import pytest

from pptax.engine.fifo import FifoBestand
from pptax.engine.vp_integration import apply_vorabpauschalen
from pptax.models.portfolio import (
    Security,
    FondsTyp,
    Transaction,
    TransaktionsTyp,
    HistorischerKurs,
)
from pptax.engine.kurs_utils import build_kurse_map


def _make_security(uuid: str = "sec-001") -> Security:
    return Security(uuid=uuid, name="Test ETF", isin="DE000TEST001", fonds_typ=FondsTyp.AKTIENFONDS)


def _make_kurse_map(sec_uuid: str, kurse: dict[str, Decimal]) -> dict[str, dict[str, Decimal]]:
    """Hilfsfunktion: erzeugt kurse_map direkt aus datum_iso -> kurs."""
    return {sec_uuid: kurse}


class TestApplyVorabpauschalen:
    def test_single_lot_one_year(self):
        """Einzelnes Lot, ein Jahr VP (2024, Verkauf 2025)."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2023, 6, 1), Decimal("100"), Decimal("90.00"))
        positionen = {"sec-001": fifo}

        sec = _make_security()
        # Kurse: Anfang 2024 = 100, Ende 2024 = 110 -> Wertsteigerung 10*100=1000
        kurse_map = _make_kurse_map("sec-001", {
            "2024-01-02": Decimal("100"),
            "2024-12-30": Decimal("110"),
        })

        apply_vorabpauschalen(
            positionen=positionen,
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[],
            steuerjahr=2025,
        )

        lots = fifo.bestand()
        assert lots[0].vorabpauschalen_kumuliert > Decimal("0")

    def test_single_lot_multi_year_with_negative_basiszins(self):
        """Mehrere Jahre VP, negative Basiszins-Jahre werden übersprungen."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2020, 1, 15), Decimal("100"), Decimal("80.00"))
        positionen = {"sec-001": fifo}

        sec = _make_security()
        # Kurse für 2020-2024
        kurse_map = _make_kurse_map("sec-001", {
            "2020-01-02": Decimal("80"),
            "2020-12-30": Decimal("90"),
            "2021-01-04": Decimal("90"),  # 2021: Basiszins negativ -> skip
            "2021-12-30": Decimal("100"),
            "2022-01-03": Decimal("100"),  # 2022: Basiszins negativ -> skip
            "2022-12-30": Decimal("95"),
            "2023-01-02": Decimal("95"),
            "2023-12-29": Decimal("110"),
            "2024-01-02": Decimal("110"),
            "2024-12-30": Decimal("120"),
        })

        apply_vorabpauschalen(
            positionen=positionen,
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[],
            steuerjahr=2025,
        )

        lots = fifo.bestand()
        # VP should be > 0 (from 2020, 2023, 2024 - positive basiszins years)
        # 2021 and 2022 have negative basiszins -> skipped
        assert lots[0].vorabpauschalen_kumuliert > Decimal("0")

    def test_unterjähriger_kauf(self):
        """Unterjähriger Kauf: VP wird anteilig berechnet."""
        # Kauf im Juli 2024 -> 6 volle Monate (Jan-Jun) vor Kauf
        # Faktor = (12 - 6) / 12 = 0.5
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2024, 7, 1), Decimal("100"), Decimal("100.00"))
        positionen = {"sec-001": fifo}

        sec = _make_security()
        kurse_map = _make_kurse_map("sec-001", {
            "2024-01-02": Decimal("100"),
            "2024-12-30": Decimal("120"),
        })

        apply_vorabpauschalen(
            positionen=positionen,
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[],
            steuerjahr=2025,
        )

        # Auch: Kauf im Januar -> volle VP
        fifo_jan = FifoBestand("sec-001")
        fifo_jan.kauf(date(2024, 1, 15), Decimal("100"), Decimal("100.00"))
        positionen_jan = {"sec-001": fifo_jan}

        apply_vorabpauschalen(
            positionen=positionen_jan,
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[],
            steuerjahr=2025,
        )

        vp_jul = fifo.bestand()[0].vorabpauschalen_kumuliert
        vp_jan = fifo_jan.bestand()[0].vorabpauschalen_kumuliert
        # Juli-Kauf sollte weniger VP haben als Januar-Kauf
        assert vp_jul < vp_jan
        assert vp_jul > Decimal("0")

    def test_mehrere_lots_individuelle_vp(self):
        """Mehrere Lots mit verschiedenen Kaufdaten -> individuelle VP."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2023, 1, 15), Decimal("50"), Decimal("90.00"))
        fifo.kauf(date(2024, 6, 1), Decimal("100"), Decimal("105.00"))
        positionen = {"sec-001": fifo}

        sec = _make_security()
        kurse_map = _make_kurse_map("sec-001", {
            "2023-01-02": Decimal("90"),
            "2023-12-29": Decimal("100"),
            "2024-01-02": Decimal("100"),
            "2024-12-30": Decimal("110"),
        })

        apply_vorabpauschalen(
            positionen=positionen,
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[],
            steuerjahr=2025,
        )

        lots = fifo.bestand()
        # Lot 1 (2023): VP für 2023 + 2024
        # Lot 2 (2024): VP nur für 2024 (unterjährig)
        assert lots[0].vorabpauschalen_kumuliert > lots[1].vorabpauschalen_kumuliert

    def test_fehlende_kursdaten_skip(self):
        """Fehlende Kursdaten -> Jahr wird übersprungen."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2023, 1, 15), Decimal("100"), Decimal("90.00"))
        positionen = {"sec-001": fifo}

        sec = _make_security()
        # Nur Kurse für 2024, nicht für 2023
        kurse_map = _make_kurse_map("sec-001", {
            "2024-01-02": Decimal("100"),
            "2024-12-30": Decimal("110"),
        })

        apply_vorabpauschalen(
            positionen=positionen,
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[],
            steuerjahr=2025,
        )

        lots = fifo.bestand()
        # Nur VP für 2024 (2023 hat keine Kurse)
        assert lots[0].vorabpauschalen_kumuliert > Decimal("0")

    def test_dividenden_reduzieren_vp(self):
        """Dividenden reduzieren die Vorabpauschale."""
        sec = _make_security()
        kurse_map = _make_kurse_map("sec-001", {
            "2024-01-02": Decimal("100"),
            "2024-12-30": Decimal("110"),
        })

        # Ohne Dividenden
        fifo_ohne = FifoBestand("sec-001")
        fifo_ohne.kauf(date(2023, 1, 1), Decimal("100"), Decimal("90.00"))
        apply_vorabpauschalen(
            positionen={"sec-001": fifo_ohne},
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[],
            steuerjahr=2025,
        )

        # Mit Dividenden
        fifo_mit = FifoBestand("sec-001")
        fifo_mit.kauf(date(2023, 1, 1), Decimal("100"), Decimal("90.00"))
        dividende = Transaction(
            datum=date(2024, 6, 15),
            typ=TransaktionsTyp.DIVIDENDE,
            security_uuid="sec-001",
            stuecke=Decimal("100"),
            kurs=Decimal("0"),
            gesamtbetrag=Decimal("200"),
        )
        apply_vorabpauschalen(
            positionen={"sec-001": fifo_mit},
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[dividende],
            steuerjahr=2025,
        )

        vp_ohne = fifo_ohne.bestand()[0].vorabpauschalen_kumuliert
        vp_mit = fifo_mit.bestand()[0].vorabpauschalen_kumuliert
        assert vp_mit < vp_ohne

    def test_steuerjahr_none_equivalent(self):
        """Ohne VP-Anwendung bleiben Lots bei 0."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2023, 1, 15), Decimal("100"), Decimal("90.00"))
        assert fifo.bestand()[0].vorabpauschalen_kumuliert == Decimal("0")

    def test_verkauf_mit_vp_reduziert_gewinn(self):
        """VP-Anrechnung reduziert den steuerpflichtigen Gewinn bei Verkauf."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2023, 1, 15), Decimal("100"), Decimal("90.00"))
        positionen = {"sec-001": fifo}

        sec = _make_security()
        kurse_map = _make_kurse_map("sec-001", {
            "2024-01-02": Decimal("100"),
            "2024-12-30": Decimal("110"),
        })

        apply_vorabpauschalen(
            positionen=positionen,
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[],
            steuerjahr=2025,
        )

        vp_kumuliert = fifo.bestand()[0].vorabpauschalen_kumuliert
        assert vp_kumuliert > Decimal("0")

        # Verkauf
        ergebnis = fifo.verkauf(date(2025, 3, 1), Decimal("100"), Decimal("120.00"))
        assert len(ergebnis) == 1
        assert ergebnis[0].vorabpauschalen_angerechnet == vp_kumuliert
        # Steuerpflichtiger Gewinn = brutto - VP
        steuerpflichtig = ergebnis[0].gewinn_brutto - ergebnis[0].vorabpauschalen_angerechnet
        assert steuerpflichtig < ergebnis[0].gewinn_brutto

    def test_wertverlust_keine_vp(self):
        """Bei Wertverlust im Jahr gibt es keine VP."""
        fifo = FifoBestand("sec-001")
        fifo.kauf(date(2023, 1, 15), Decimal("100"), Decimal("110.00"))
        positionen = {"sec-001": fifo}

        sec = _make_security()
        # Kurs fällt 2024
        kurse_map = _make_kurse_map("sec-001", {
            "2024-01-02": Decimal("110"),
            "2024-12-30": Decimal("100"),
        })

        apply_vorabpauschalen(
            positionen=positionen,
            securities={"sec-001": sec},
            kurse_map=kurse_map,
            transactions=[],
            steuerjahr=2025,
        )

        assert fifo.bestand()[0].vorabpauschalen_kumuliert == Decimal("0")

    def test_unknown_security_skipped(self):
        """Unbekannte Security wird übersprungen."""
        fifo = FifoBestand("sec-unknown")
        fifo.kauf(date(2023, 1, 15), Decimal("100"), Decimal("90.00"))
        positionen = {"sec-unknown": fifo}

        apply_vorabpauschalen(
            positionen=positionen,
            securities={},  # no securities
            kurse_map={},
            transactions=[],
            steuerjahr=2025,
        )

        assert fifo.bestand()[0].vorabpauschalen_kumuliert == Decimal("0")
