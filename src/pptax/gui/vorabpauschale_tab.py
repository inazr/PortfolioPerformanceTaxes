"""Vorabpauschale Tab."""

from datetime import date
from decimal import Decimal

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from pptax.parser.pp_xml_parser import PortfolioData
from pptax.engine.vorabpauschale import berechne_vorabpauschale
from pptax.engine.tax_params import get_param
from pptax.models.tax import VorabpauschaleErgebnis
from pptax.export.csv_export import export_vorabpauschale
from pptax.gui import _fmt


class VorabpauschaleTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.data: PortfolioData | None = None
        self._ergebnisse: list[VorabpauschaleErgebnis] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Jahr-Auswahl
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Steuerjahr:"))
        self.year_combo = QComboBox()
        current_year = date.today().year
        for y in range(current_year, 2017, -1):
            self.year_combo.addItem(str(y))
        top_layout.addWidget(self.year_combo)

        btn_calc = QPushButton("Berechnen")
        btn_calc.clicked.connect(self._calculate)
        top_layout.addWidget(btn_calc)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Warnung
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: orange; font-weight: bold;")
        layout.addWidget(self.warning_label)

        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Wertpapier", "ISIN", "Wert 01.01.", "Wert 31.12.",
            "Basisertrag", "Vorabpauschale", "Teilfreistellung",
            "Steuerpflichtig", "Steuer",
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

        # Summe
        self.sum_label = QLabel("")
        self.sum_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.sum_label)

    def update_data(self, data: PortfolioData):
        self.data = data

    def _calculate(self):
        if not self.data:
            return

        jahr = int(self.year_combo.currentText())

        # Prüfe ob Basiszins negativ
        try:
            basiszins = get_param("basiszins_vorabpauschale", jahr)
            if basiszins < 0:
                self.warning_label.setText(
                    f"Basiszins {jahr} ist negativ ({basiszins}) – "
                    f"keine Vorabpauschale fällig."
                )
            else:
                self.warning_label.setText("")
        except ValueError:
            self.warning_label.setText(f"Keine Daten für Jahr {jahr} verfügbar.")
            return

        # Kurse für Jahresanfang/-ende suchen
        kurse_map: dict[str, dict[str, Decimal]] = {}
        for k in self.data.kurse:
            if k.security_uuid not in kurse_map:
                kurse_map[k.security_uuid] = {}
            kurse_map[k.security_uuid][k.datum.isoformat()] = k.kurs

        self._ergebnisse = []
        for sec in self.data.securities:
            sec_kurse = kurse_map.get(sec.uuid, {})

            # Finde nächsten Kurs zum 1.1. und 31.12.
            wert_anfang = self._find_nearest_kurs(
                sec_kurse, date(jahr, 1, 1)
            )
            wert_ende = self._find_nearest_kurs(
                sec_kurse, date(jahr, 12, 31)
            )

            if wert_anfang is None or wert_ende is None:
                continue

            # Ausschüttungen im Jahr
            ausschuettungen = Decimal("0")
            from pptax.models.portfolio import TransaktionsTyp
            for tx in self.data.transactions:
                if (
                    tx.security_uuid == sec.uuid
                    and tx.typ == TransaktionsTyp.DIVIDENDE
                    and tx.datum.year == jahr
                ):
                    ausschuettungen += tx.gesamtbetrag

            try:
                erg = berechne_vorabpauschale(
                    security=sec,
                    jahr=jahr,
                    wert_anfang=wert_anfang,
                    wert_ende=wert_ende,
                    ausschuettungen=ausschuettungen,
                )
                self._ergebnisse.append(erg)
            except ValueError:
                continue

        self._update_table()

    def _find_nearest_kurs(
        self, kurse: dict[str, Decimal], target: date
    ) -> Decimal | None:
        """Finde den nächsten Kurs zu einem Stichtag."""
        if not kurse:
            return None
        target_str = target.isoformat()
        if target_str in kurse:
            return kurse[target_str]
        # Suche nächsten Kurs innerhalb von 5 Tagen
        from datetime import timedelta
        for delta in range(1, 6):
            for d in [target - timedelta(days=delta), target + timedelta(days=delta)]:
                if d.isoformat() in kurse:
                    return kurse[d.isoformat()]
        return None

    def _update_table(self):
        self.table.setRowCount(len(self._ergebnisse))
        steuer_summe = Decimal("0")

        sec_map = {}
        if self.data:
            sec_map = {s.uuid: s for s in self.data.securities}

        for i, e in enumerate(self._ergebnisse):
            sec = sec_map.get(e.security_uuid)
            name = sec.name if sec else e.security_uuid
            isin = sec.isin if sec else ""

            items = [
                name,
                isin or "",
                _fmt.euro(e.wert_jahresanfang),
                _fmt.euro(e.wert_jahresende),
                _fmt.euro(e.basisertrag),
                _fmt.euro(e.vorabpauschale_brutto),
                _fmt.percent(e.teilfreistellung_satz),
                _fmt.euro(e.vorabpauschale_steuerpflichtig),
                _fmt.euro(e.steuer),
            ]
            for j, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j >= 2:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(i, j, item)

            steuer_summe += e.steuer

        self.sum_label.setText(f"Steuer gesamt: {_fmt.euro(steuer_summe)}")

    def export_csv(self):
        if not self._ergebnisse:
            QMessageBox.warning(self, "Export", "Keine Daten zum Exportieren.")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Vorabpauschale exportieren", "vorabpauschale.csv",
            "CSV Dateien (*.csv)"
        )
        if filepath:
            sec_map = {s.uuid: s for s in self.data.securities} if self.data else {}
            export_vorabpauschale(self._ergebnisse, sec_map, filepath)
            QMessageBox.information(self, "Export", "Export erfolgreich.")
