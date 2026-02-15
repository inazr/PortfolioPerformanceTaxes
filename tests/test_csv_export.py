"""Tests für CSV Export."""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from pptax.models.portfolio import Security, FondsTyp
from pptax.models.tax import (
    VorabpauschaleErgebnis,
    FreibetragOptimierungErgebnis,
    VerkaufsVorschlag,
    NettoBetragPlan,
)
from pptax.export.csv_export import (
    export_vorabpauschale,
    export_freibetrag,
    export_verkaufsplan,
)


class TestCSVExport:
    def test_vorabpauschale_export(self, tmp_path):
        """CSV-Export der Vorabpauschale."""
        ergebnis = VorabpauschaleErgebnis(
            security_uuid="s1",
            jahr=2023,
            wert_jahresanfang=Decimal("10000"),
            wert_jahresende=Decimal("12000"),
            basiszins=Decimal("0.0255"),
            basisertrag=Decimal("178.50"),
            wertsteigerung=Decimal("2000"),
            ausschuettungen=Decimal("0"),
            vorabpauschale_brutto=Decimal("178.50"),
            teilfreistellung_satz=Decimal("0.30"),
            vorabpauschale_steuerpflichtig=Decimal("124.95"),
            steuer=Decimal("32.96"),
        )
        sec = Security(uuid="s1", name="Test ETF", isin="IE001", fonds_typ=FondsTyp.AKTIENFONDS)

        filepath = tmp_path / "vp.csv"
        export_vorabpauschale([ergebnis], {"s1": sec}, filepath)

        content = filepath.read_text(encoding="utf-8-sig")
        assert "Test ETF" in content
        assert "IE001" in content
        # German format: semicolon delimiter
        assert ";" in content

    def test_freibetrag_export(self, tmp_path):
        """CSV-Export der Freibetrag-Optimierung."""
        vorschlag = VerkaufsVorschlag(
            security_uuid="s1",
            security_name="Test ETF",
            isin="IE001",
            stuecke=Decimal("10"),
            kaufdatum=date(2020, 1, 1),
            einstandskurs=Decimal("50"),
            aktueller_kurs=Decimal("100"),
            brutto_erloes=Decimal("1000"),
            gewinn_brutto=Decimal("500"),
            teilfreistellung_satz=Decimal("0.30"),
            gewinn_steuerpflichtig=Decimal("350"),
            steuer=Decimal("0"),
            netto_erloes=Decimal("1000"),
        )
        ergebnis = FreibetragOptimierungErgebnis(
            jahr=2023,
            freibetrag_gesamt=Decimal("1000"),
            freibetrag_bereits_genutzt=Decimal("0"),
            freibetrag_verbleibend=Decimal("1000"),
            verkaufsempfehlungen=[vorschlag],
        )

        filepath = tmp_path / "fb.csv"
        export_freibetrag(ergebnis, filepath)

        content = filepath.read_text(encoding="utf-8-sig")
        assert "Test ETF" in content

    def test_bom_present(self, tmp_path):
        """UTF-8 BOM für Excel-Kompatibilität."""
        ergebnis = FreibetragOptimierungErgebnis(
            jahr=2023,
            freibetrag_gesamt=Decimal("1000"),
            freibetrag_bereits_genutzt=Decimal("0"),
            freibetrag_verbleibend=Decimal("1000"),
        )

        filepath = tmp_path / "bom.csv"
        export_freibetrag(ergebnis, filepath)

        raw = filepath.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf"  # UTF-8 BOM

    def test_german_number_format(self, tmp_path):
        """Deutsche Zahlenformatierung (Komma als Dezimalzeichen)."""
        ergebnis = VorabpauschaleErgebnis(
            security_uuid="s1",
            jahr=2023,
            wert_jahresanfang=Decimal("10000.50"),
            wert_jahresende=Decimal("12000"),
            basiszins=Decimal("0.0255"),
            basisertrag=Decimal("178.50"),
            wertsteigerung=Decimal("1999.50"),
            ausschuettungen=Decimal("0"),
            vorabpauschale_brutto=Decimal("178.50"),
            teilfreistellung_satz=Decimal("0.30"),
            vorabpauschale_steuerpflichtig=Decimal("124.95"),
            steuer=Decimal("32.96"),
        )
        sec = Security(uuid="s1", name="Test", fonds_typ=FondsTyp.AKTIENFONDS)

        filepath = tmp_path / "num.csv"
        export_vorabpauschale([ergebnis], {"s1": sec}, filepath)

        content = filepath.read_text(encoding="utf-8-sig")
        # German: comma as decimal separator
        assert "10000,50" in content or "10.000,50" in content
