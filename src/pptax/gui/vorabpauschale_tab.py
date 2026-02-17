"""Vorabpauschale Tab."""

from datetime import date
from decimal import Decimal

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
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
from pptax.engine.kurs_utils import build_kurse_map, find_nearest_kurs
from pptax.engine.tax_params import get_param
from pptax.models.portfolio import TransaktionsTyp
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

        # Berechnen-Button
        top_layout = QHBoxLayout()
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
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Jahr", "Wertpapier", "ISIN", "Wert 01.01.", "Wert 31.12.",
            "Basisertrag", "Vorabpauschale", "Teilfreistellung",
            "Steuerpflichtig", "Steuer",
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

        # Summe
        self.sum_label = QLabel("")
        self.sum_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.sum_label)

    def update_data(self, data: PortfolioData):
        self.data = data

    def _get_available_years(self) -> list[int]:
        """Ermittle alle Jahre, für die Kursdaten vorhanden sind."""
        if not self.data:
            return []
        years: set[int] = set()
        for k in self.data.kurse:
            years.add(k.datum.year)
        return sorted(years, reverse=True)

    def _calculate(self):
        if not self.data:
            return

        kurse_map = build_kurse_map(self.data.kurse)
        available_years = self._get_available_years()

        # Warnungen für Jahre mit negativem Basiszins sammeln
        negative_years: list[str] = []

        self._ergebnisse = []
        for jahr in available_years:
            try:
                basiszins = get_param("basiszins_vorabpauschale", jahr)
            except ValueError:
                continue

            if basiszins < 0:
                negative_years.append(f"{jahr} ({basiszins})")

            for sec in self.data.securities:
                sec_kurse = kurse_map.get(sec.uuid, {})

                wert_anfang = find_nearest_kurs(sec_kurse, date(jahr, 1, 1))
                wert_ende = find_nearest_kurs(sec_kurse, date(jahr, 12, 31))

                if wert_anfang is None or wert_ende is None:
                    continue

                # Ausschüttungen im Jahr
                ausschuettungen = Decimal("0")
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

        if negative_years:
            self.warning_label.setText(
                "Negativer Basiszins (keine VP fällig): "
                + ", ".join(negative_years)
            )
        else:
            self.warning_label.setText("")

        self._update_table()

    def _update_table(self):
        sec_map = {}
        if self.data:
            sec_map = {s.uuid: s for s in self.data.securities}

        # Sortierung: Jahr DESC, Wertpapier-Name ASC
        def sort_key(e: VorabpauschaleErgebnis):
            sec = sec_map.get(e.security_uuid)
            name = sec.name if sec else e.security_uuid
            return (-e.jahr, name.lower())

        sorted_ergebnisse = sorted(self._ergebnisse, key=sort_key)

        # Ergebnisse nach Jahr gruppieren für Zwischensummen
        jahre_in_order: list[int] = []
        for e in sorted_ergebnisse:
            if not jahre_in_order or jahre_in_order[-1] != e.jahr:
                jahre_in_order.append(e.jahr)

        # Zähle Zeilen: Ergebnisse + Zwischensummen pro Jahr
        row_count = len(sorted_ergebnisse) + len(jahre_in_order)
        self.table.setRowCount(row_count)

        steuer_gesamt = Decimal("0")
        row = 0
        current_jahr = None
        jahr_steuer = Decimal("0")

        for e in sorted_ergebnisse:
            # Zwischensumme für vorheriges Jahr einfügen
            if current_jahr is not None and e.jahr != current_jahr:
                self._insert_subtotal_row(row, current_jahr, jahr_steuer)
                row += 1
                jahr_steuer = Decimal("0")

            current_jahr = e.jahr
            sec = sec_map.get(e.security_uuid)
            name = sec.name if sec else e.security_uuid
            isin = sec.isin if sec else ""

            items = [
                str(e.jahr),
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
                if j >= 3:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, j, item)

            jahr_steuer += e.steuer
            steuer_gesamt += e.steuer
            row += 1

        # Letzte Zwischensumme
        if current_jahr is not None:
            self._insert_subtotal_row(row, current_jahr, jahr_steuer)

        self.sum_label.setText(f"Steuer gesamt: {_fmt.euro(steuer_gesamt)}")

    def _insert_subtotal_row(self, row: int, jahr: int, steuer: Decimal):
        """Fügt eine fett formatierte Zwischensummen-Zeile ein."""
        bg_color = QColor(240, 240, 240)
        bold_font_items = [
            (0, f"Summe {jahr}"),
            (9, _fmt.euro(steuer)),
        ]
        for col in range(self.table.columnCount()):
            item = QTableWidgetItem("")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setBackground(bg_color)
            self.table.setItem(row, col, item)

        for col, text in bold_font_items:
            item = self.table.item(row, col)
            item.setText(text)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            if col >= 3:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )

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
