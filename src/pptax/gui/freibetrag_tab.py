"""Freibetrag-Optimierung Tab."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from pptax.parser.pp_xml_parser import PortfolioData
from pptax.models.portfolio import TransaktionsTyp
from pptax.engine.fifo import FifoBestand
from pptax.engine.freibetrag import optimiere_freibetrag
from pptax.engine.kurs_utils import build_kurse_map
from pptax.engine.vp_integration import apply_vorabpauschalen
from pptax.engine.tax_params import get_param
from pptax.models.tax import FreibetragOptimierungErgebnis, VerkaufsVorschlag
from pptax.export.csv_export import export_freibetrag
from pptax.gui import _fmt

HEADERS = [
    "Wertpapier", "ISIN", "Stücke", "Kaufdatum",
    "Einstandskurs", "Aktueller Kurs", "Gewinn stpfl.", "Steuer",
]


class FreibetragTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.data: PortfolioData | None = None
        self._ergebnis: FreibetragOptimierungErgebnis | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Freibetrag-Anzeige + Jahrwahl
        info_layout = QHBoxLayout()
        self.freibetrag_label = QLabel("Freibetrag: – / – / –")
        self.freibetrag_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(self.freibetrag_label)

        info_layout.addWidget(QLabel("Steuerjahr:"))
        self.year_combo = QComboBox()
        current_year = date.today().year
        for y in range(current_year, 2017, -1):
            self.year_combo.addItem(str(y))
        info_layout.addWidget(self.year_combo)

        btn_calc = QPushButton("Optimale Verkäufe berechnen")
        btn_calc.clicked.connect(self._calculate)
        info_layout.addWidget(btn_calc)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Info-Text
        info_text = QLabel(
            "Strategie: Verkauf und sofortiger Rückkauf zum neuen Einstandskurs. "
            "Steuer = 0 € (innerhalb Freibetrag). Effekt: Einstandskurs wird "
            "angehoben → weniger Steuern bei späterem echten Verkauf."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: gray; margin: 5px 0;")
        layout.addWidget(info_text)

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
        self._update_freibetrag_display()

    def _update_freibetrag_display(self):
        config = self.main_window.config
        jahr = int(self.year_combo.currentText())
        try:
            spb = get_param("sparerpauschbetrag", jahr)
            gesamt = Decimal(str(spb[config.veranlagungstyp]))
            genutzt = config.freibetrag_bereits_genutzt
            verbleibend = max(Decimal("0"), gesamt - genutzt)
            self.freibetrag_label.setText(
                f"Freibetrag: {_fmt.euro(gesamt)} gesamt / "
                f"{_fmt.euro(genutzt)} genutzt / "
                f"{_fmt.euro(verbleibend)} verbleibend"
            )
        except ValueError:
            self.freibetrag_label.setText("Freibetrag: nicht verfügbar")

    def _calculate(self):
        if not self.data:
            return

        config = self.main_window.config
        jahr = int(self.year_combo.currentText())

        # FIFO-Bestände aufbauen
        positionen, aktuelle_kurse = _build_fifo_from_data(self.data, steuerjahr=jahr)

        sec_map = {s.uuid: s for s in self.data.securities}

        self._ergebnis = optimiere_freibetrag(
            jahr=jahr,
            veranlagungstyp=config.veranlagungstyp,
            bereits_genutzt=config.freibetrag_bereits_genutzt,
            positionen=positionen,
            aktuelle_kurse=aktuelle_kurse,
            securities=sec_map,
        )

        self._update_freibetrag_display()
        self._update_tree()

    def _update_tree(self):
        if not self._ergebnis:
            return

        self.tree.clear()
        empf = self._ergebnis.verkaufsempfehlungen

        # Gruppiere Vorschläge nach security_uuid (Reihenfolge beibehalten)
        grouped: dict[str, list[VerkaufsVorschlag]] = defaultdict(list)
        order: list[str] = []
        for v in empf:
            if v.security_uuid not in grouped:
                order.append(v.security_uuid)
            grouped[v.security_uuid].append(v)

        bold_font = QFont()
        bold_font.setBold(True)
        gray_color = QColor(100, 100, 100)

        for uuid in order:
            lots = grouped[uuid]

            if len(lots) > 1:
                # Zusammenfassungszeile als Parent-Item
                total_stuecke = sum(v.stuecke for v in lots)
                total_gewinn_stpfl = sum(v.gewinn_steuerpflichtig for v in lots)
                total_steuer = sum(v.steuer for v in lots)
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
                    _fmt.euro(total_gewinn_stpfl),
                    _fmt.euro(total_steuer),
                ])
                for col in range(len(HEADERS)):
                    parent.setFont(col, bold_font)
                    if col >= 2:
                        parent.setTextAlignment(
                            col,
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        )

                # Lot-Detail-Zeilen als Children
                for v in lots:
                    child = QTreeWidgetItem(parent, [
                        f"Lot {v.kaufdatum.strftime('%d.%m.%Y')}",
                        "",
                        _fmt.decimal(v.stuecke),
                        v.kaufdatum.strftime("%d.%m.%Y") if v.kaufdatum else "",
                        _fmt.euro(v.einstandskurs),
                        _fmt.euro(v.aktueller_kurs),
                        _fmt.euro(v.gewinn_steuerpflichtig),
                        _fmt.euro(v.steuer),
                    ])
                    for col in range(len(HEADERS)):
                        child.setForeground(col, gray_color)
                        if col >= 2:
                            child.setTextAlignment(
                                col,
                                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                            )

                # Default: zugeklappt
                parent.setExpanded(False)
            else:
                # Einzelnes Lot — Top-Level ohne Children
                v = lots[0]
                item = QTreeWidgetItem(self.tree, [
                    v.security_name,
                    v.isin or "",
                    _fmt.decimal(v.stuecke),
                    v.kaufdatum.strftime("%d.%m.%Y") if v.kaufdatum else "",
                    _fmt.euro(v.einstandskurs),
                    _fmt.euro(v.aktueller_kurs),
                    _fmt.euro(v.gewinn_steuerpflichtig),
                    _fmt.euro(v.steuer),
                ])
                for col in range(len(HEADERS)):
                    if col >= 2:
                        item.setTextAlignment(
                            col,
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        )

    def export_csv(self):
        if not self._ergebnis:
            QMessageBox.warning(self, "Export", "Keine Daten zum Exportieren.")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Freibetrag exportieren", "freibetrag.csv",
            "CSV Dateien (*.csv)"
        )
        if filepath:
            export_freibetrag(self._ergebnis, filepath)
            QMessageBox.information(self, "Export", "Export erfolgreich.")


def _build_fifo_from_data(
    data: PortfolioData,
    steuerjahr: int | None = None,
) -> tuple[dict[str, FifoBestand], dict[str, Decimal]]:
    """Baue FIFO-Bestände und aktuelle Kurse aus den Portfolio-Daten.

    Wenn steuerjahr angegeben, werden Vorabpauschalen für alle
    abgeschlossenen Jahre vor dem Steuerjahr auf die Lots angewendet.
    """
    positionen: dict[str, FifoBestand] = {}

    # Transaktionen nach Datum sortieren
    sorted_tx = sorted(data.transactions, key=lambda t: t.datum)
    for tx in sorted_tx:
        if tx.typ == TransaktionsTyp.KAUF or tx.typ == TransaktionsTyp.EINLIEFERUNG:
            if tx.security_uuid not in positionen:
                positionen[tx.security_uuid] = FifoBestand(tx.security_uuid)
            positionen[tx.security_uuid].kauf(tx.datum, tx.stuecke, tx.kurs)
        elif tx.typ == TransaktionsTyp.VERKAUF or tx.typ == TransaktionsTyp.AUSLIEFERUNG:
            if tx.security_uuid in positionen:
                try:
                    positionen[tx.security_uuid].verkauf(
                        tx.datum, tx.stuecke, tx.kurs
                    )
                except ValueError:
                    pass

    # Vorabpauschalen anwenden
    if steuerjahr is not None:
        sec_map = {s.uuid: s for s in data.securities}
        kurse_map = build_kurse_map(data.kurse)
        apply_vorabpauschalen(positionen, sec_map, kurse_map, data.transactions, steuerjahr)

    # Aktuelle Kurse: neuester verfügbarer Kurs pro Security
    aktuelle_kurse: dict[str, Decimal] = {}
    for k in sorted(data.kurse, key=lambda x: x.datum):
        aktuelle_kurse[k.security_uuid] = k.kurs

    return positionen, aktuelle_kurse
