"""Dashboard / Übersicht Tab."""

from decimal import Decimal

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QFileDialog,
    QHeaderView,
)
from PyQt6.QtCore import Qt

from pptax.models.portfolio import FondsTyp, Security
from pptax.parser.pp_xml_parser import PortfolioData
from pptax.gui import _fmt


class DashboardTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._fondstyp_combos: dict[str, QComboBox] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Datei laden
        file_group = QGroupBox("Portfolio Performance Datei")
        file_layout = QHBoxLayout()
        self.file_label = QLabel("Keine Datei geladen")
        btn_open = QPushButton("Datei öffnen...")
        btn_open.clicked.connect(self.main_window._open_file_dialog)
        file_layout.addWidget(self.file_label, 1)
        file_layout.addWidget(btn_open)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Konfiguration
        config_group = QGroupBox("Steuerliche Konfiguration")
        config_layout = QHBoxLayout()

        config_layout.addWidget(QLabel("Veranlagung:"))
        self.veranlagung_combo = QComboBox()
        self.veranlagung_combo.addItems(["Einzelveranlagung", "Zusammenveranlagung"])
        self.veranlagung_combo.currentIndexChanged.connect(self._on_config_changed)
        config_layout.addWidget(self.veranlagung_combo)

        self.kirchensteuer_check = QCheckBox("Kirchensteuer")
        self.kirchensteuer_check.stateChanged.connect(self._on_config_changed)
        config_layout.addWidget(self.kirchensteuer_check)

        config_layout.addWidget(QLabel("Bundesland:"))
        self.bundesland_combo = QComboBox()
        self.bundesland_combo.addItems([
            "Standard (9%)", "Bayern (8%)", "Baden-Württemberg (8%)"
        ])
        self.bundesland_combo.currentIndexChanged.connect(self._on_config_changed)
        config_layout.addWidget(self.bundesland_combo)

        config_layout.addWidget(QLabel("Freibetrag bereits genutzt (€):"))
        self.freibetrag_input = QLineEdit("0")
        self.freibetrag_input.setMaximumWidth(100)
        self.freibetrag_input.editingFinished.connect(self._on_config_changed)
        config_layout.addWidget(self.freibetrag_input)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Zusammenfassung
        self.summary_label = QLabel("Bitte laden Sie eine Portfolio Performance Datei.")
        layout.addWidget(self.summary_label)

        # Wertpapier-Tabelle mit FondsTyp-Zuordnung
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Wertpapier", "ISIN", "WKN", "UUID", "Fondstyp"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

    def _on_config_changed(self):
        config = self.main_window.config
        config.veranlagungstyp = (
            "single" if self.veranlagung_combo.currentIndex() == 0 else "joint"
        )
        config.kirchensteuer = self.kirchensteuer_check.isChecked()
        bundesland_map = {0: "default", 1: "bayern", 2: "baden_wuerttemberg"}
        config.bundesland = bundesland_map.get(
            self.bundesland_combo.currentIndex(), "default"
        )
        try:
            text = self.freibetrag_input.text().replace(",", ".")
            config.freibetrag_bereits_genutzt = Decimal(text)
        except Exception:
            config.freibetrag_bereits_genutzt = Decimal("0")

    def update_data(self, data: PortfolioData):
        self.file_label.setText(
            f"{len(data.securities)} Wertpapiere, "
            f"{len(data.transactions)} Transaktionen, "
            f"{len(data.kurse)} Kurse"
        )
        self.summary_label.setText(
            f"Portfolio geladen: {len(data.securities)} Wertpapiere"
        )

        self.table.setRowCount(len(data.securities))
        self._fondstyp_combos.clear()

        fondstyp_labels = [
            "Aktienfonds", "Mischfonds", "Immobilienfonds (Inland)",
            "Immobilienfonds (Ausland)", "Sonstige"
        ]
        fondstyp_values = list(FondsTyp)

        for i, sec in enumerate(data.securities):
            self.table.setItem(i, 0, QTableWidgetItem(sec.name))
            self.table.setItem(i, 1, QTableWidgetItem(sec.isin or ""))
            self.table.setItem(i, 2, QTableWidgetItem(sec.wkn or ""))
            self.table.setItem(i, 3, QTableWidgetItem(sec.uuid))

            combo = QComboBox()
            combo.addItems(fondstyp_labels)
            combo.setCurrentIndex(fondstyp_values.index(sec.fonds_typ))
            combo.currentIndexChanged.connect(
                lambda idx, s=sec: setattr(s, "fonds_typ", fondstyp_values[idx])
            )
            self.table.setCellWidget(i, 4, combo)
            self._fondstyp_combos[sec.uuid] = combo
