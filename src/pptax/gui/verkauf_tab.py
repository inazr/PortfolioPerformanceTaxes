"""Verkaufsplanung Tab."""

from datetime import date
from decimal import Decimal

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from pptax.engine.verkauf import plane_netto_verkauf
from pptax.models.tax import NettoBetragPlan
from pptax.export.csv_export import export_verkaufsplan
from pptax.gui import _fmt
from pptax.gui.freibetrag_tab import _build_fifo_from_data


class VerkaufTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.data: PortfolioData | None = None
        self._plan: NettoBetragPlan | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Eingabe
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Ich brauche netto:"))
        self.netto_input = QLineEdit()
        self.netto_input.setPlaceholderText("z.B. 5000")
        self.netto_input.setMaximumWidth(150)
        input_layout.addWidget(self.netto_input)
        input_layout.addWidget(QLabel("€"))

        btn_calc = QPushButton("Berechnen")
        btn_calc.clicked.connect(self._calculate)
        input_layout.addWidget(btn_calc)
        input_layout.addStretch()
        layout.addLayout(input_layout)

        # Zusammenfassung
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.summary_label)

        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Wertpapier", "ISIN", "Stücke", "Kauf am",
            "Einstand", "Aktuell", "Gewinn", "Steuer", "Netto",
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

    def update_data(self, data: PortfolioData):
        self.data = data

    def _calculate(self):
        if not self.data:
            return

        try:
            text = self.netto_input.text().replace(",", ".")
            ziel = Decimal(text)
        except Exception:
            QMessageBox.warning(self, "Eingabe", "Bitte gültigen Betrag eingeben.")
            return

        config = self.main_window.config
        jahr = date.today().year

        positionen, aktuelle_kurse = _build_fifo_from_data(self.data)
        sec_map = {s.uuid: s for s in self.data.securities}

        self._plan = plane_netto_verkauf(
            ziel_netto=ziel,
            jahr=jahr,
            veranlagungstyp=config.veranlagungstyp,
            freibetrag_genutzt=config.freibetrag_bereits_genutzt,
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=sec_map,
            kirchensteuer=config.kirchensteuer,
            bundesland=config.bundesland,
        )

        self._update_display()

    def _update_display(self):
        if not self._plan:
            return

        p = self._plan
        self.summary_label.setText(
            f"Brutto: {_fmt.euro(p.brutto_gesamt)} | "
            f"Steuer: {_fmt.euro(p.steuer_gesamt)} | "
            f"Netto: {_fmt.euro(p.erreichtes_netto)} "
            f"(Ziel: {_fmt.euro(p.ziel_netto)})"
        )

        plan = p.verkaufsplan
        self.table.setRowCount(len(plan))

        for i, v in enumerate(plan):
            items = [
                v.security_name,
                v.isin or "",
                _fmt.decimal(v.stuecke),
                v.kaufdatum.strftime("%d.%m.%Y") if v.kaufdatum else "",
                _fmt.euro(v.einstandskurs),
                _fmt.euro(v.aktueller_kurs),
                _fmt.euro(v.gewinn_brutto),
                _fmt.euro(v.steuer),
                _fmt.euro(v.netto_erloes),
            ]
            for j, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j >= 2:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                # Negative Werte in Rot
                if j >= 6:
                    try:
                        val = Decimal(
                            text.replace(".", "").replace(",", ".").replace(" €", "").replace(" ", "")
                        )
                        if val < 0:
                            item.setForeground(QColor("red"))
                    except Exception:
                        pass
                self.table.setItem(i, j, item)

    def export_csv(self):
        if not self._plan:
            QMessageBox.warning(self, "Export", "Keine Daten zum Exportieren.")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Verkaufsplan exportieren", "verkaufsplan.csv",
            "CSV Dateien (*.csv)"
        )
        if filepath:
            export_verkaufsplan(self._plan, filepath)
            QMessageBox.information(self, "Export", "Export erfolgreich.")
