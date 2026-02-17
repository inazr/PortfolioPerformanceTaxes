"""Verkaufsplanung Tab."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from pptax.parser.pp_xml_parser import PortfolioData
from pptax.engine.verkauf import plane_netto_verkauf
from pptax.models.tax import NettoBetragPlan, VerkaufsVorschlag
from pptax.export.csv_export import export_verkaufsplan
from pptax.gui import _fmt
from pptax.gui.freibetrag_tab import _build_fifo_from_data

HEADERS = [
    "Wertpapier", "ISIN", "Stücke", "Kauf am",
    "Einstand", "Aktuell", "Gewinn", "Steuer", "Netto",
]


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

        input_layout.addWidget(QLabel("Steuerjahr:"))
        self.year_combo = QComboBox()
        current_year = date.today().year
        for y in range(current_year, 2017, -1):
            self.year_combo.addItem(str(y))
        input_layout.addWidget(self.year_combo)

        btn_calc = QPushButton("Berechnen")
        btn_calc.clicked.connect(self._calculate)
        input_layout.addWidget(btn_calc)
        input_layout.addStretch()
        layout.addLayout(input_layout)

        # Zusammenfassung
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.summary_label)

        # Tree-Widget (zuklappbar)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(HEADERS))
        self.tree.setHeaderLabels(HEADERS)
        self.tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.tree.setRootIsDecorated(True)
        layout.addWidget(self.tree)

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
        jahr = int(self.year_combo.currentText())

        positionen, aktuelle_kurse = _build_fifo_from_data(self.data, steuerjahr=jahr)
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

        self.tree.clear()
        plan = p.verkaufsplan

        # Gruppiere nach security_uuid
        grouped: dict[str, list[VerkaufsVorschlag]] = defaultdict(list)
        order: list[str] = []
        for v in plan:
            if v.security_uuid not in grouped:
                order.append(v.security_uuid)
            grouped[v.security_uuid].append(v)

        bold_font = QFont()
        bold_font.setBold(True)
        gray_color = QColor(100, 100, 100)

        for uuid in order:
            lots = grouped[uuid]

            if len(lots) > 1:
                # Zusammenfassungszeile
                total_stuecke = sum(v.stuecke for v in lots)
                total_gewinn = sum(v.gewinn_brutto for v in lots)
                total_steuer = sum(v.steuer for v in lots)
                total_netto = sum(v.netto_erloes for v in lots)
                avg_einstand = (
                    sum(v.einstandskurs * v.stuecke for v in lots) / total_stuecke
                    if total_stuecke > 0
                    else Decimal("0")
                )

                first = lots[0]
                parent = QTreeWidgetItem(self.tree, [
                    first.security_name,
                    first.isin or "",
                    _fmt.decimal(total_stuecke),
                    f"({len(lots)} Lots)",
                    _fmt.euro(avg_einstand),
                    _fmt.euro(first.aktueller_kurs),
                    _fmt.euro(total_gewinn),
                    _fmt.euro(total_steuer),
                    _fmt.euro(total_netto),
                ])
                for col in range(len(HEADERS)):
                    parent.setFont(col, bold_font)
                    if col >= 2:
                        parent.setTextAlignment(
                            col,
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        )
                _color_negative_cols(parent, range(6, len(HEADERS)))

                # Lot-Details
                for v in lots:
                    child = _make_lot_item(parent, v)
                    for col in range(len(HEADERS)):
                        child.setForeground(col, gray_color)
                    _color_negative_cols(child, range(6, len(HEADERS)))

                parent.setExpanded(False)
            else:
                # Einzelnes Lot
                item = _make_lot_item(self.tree, lots[0])
                _color_negative_cols(item, range(6, len(HEADERS)))

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


def _make_lot_item(parent, v: VerkaufsVorschlag) -> QTreeWidgetItem:
    """Erstelle ein TreeWidgetItem für ein einzelnes Lot."""
    is_child = isinstance(parent, QTreeWidgetItem)
    name = f"Lot {v.kaufdatum.strftime('%d.%m.%Y')}" if is_child else v.security_name
    item = QTreeWidgetItem(parent, [
        name,
        "" if is_child else (v.isin or ""),
        _fmt.decimal(v.stuecke),
        v.kaufdatum.strftime("%d.%m.%Y") if v.kaufdatum else "",
        _fmt.euro(v.einstandskurs),
        _fmt.euro(v.aktueller_kurs),
        _fmt.euro(v.gewinn_brutto),
        _fmt.euro(v.steuer),
        _fmt.euro(v.netto_erloes),
    ])
    for col in range(len(HEADERS)):
        if col >= 2:
            item.setTextAlignment(
                col,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
    return item


def _color_negative_cols(item: QTreeWidgetItem, cols: range) -> None:
    """Färbe negative Werte in den angegebenen Spalten rot."""
    red = QColor("red")
    for col in cols:
        text = item.text(col)
        try:
            val = Decimal(
                text.replace(".", "").replace(",", ".").replace(" €", "").replace(" ", "")
            )
            if val < 0:
                item.setForeground(col, red)
        except Exception:
            pass
