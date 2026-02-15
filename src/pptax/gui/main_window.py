"""Hauptfenster mit Tab-Struktur."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QMenuBar,
    QStatusBar,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from pptax.config import AppConfig
from pptax.parser.pp_xml_parser import PortfolioData, parse_portfolio_file
from pptax.gui.dashboard_tab import DashboardTab
from pptax.gui.vorabpauschale_tab import VorabpauschaleTab
from pptax.gui.freibetrag_tab import FreibetragTab
from pptax.gui.verkauf_tab import VerkaufTab

DISCLAIMER = (
    "Dieses Tool dient der Orientierung und ersetzt keine Steuerberatung. "
    "Alle Berechnungen ohne Gewähr. Bitte konsultieren Sie einen "
    "Steuerberater für verbindliche Auskünfte."
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SteuerPP – Steuerrechner für Portfolio Performance")
        self.setMinimumSize(1000, 700)

        self.config = AppConfig()
        self.portfolio_data: PortfolioData | None = None

        self._setup_ui()
        self._setup_menu()
        self._show_disclaimer()

    def _setup_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard_tab = DashboardTab(self)
        self.vorabpauschale_tab = VorabpauschaleTab(self)
        self.freibetrag_tab = FreibetragTab(self)
        self.verkauf_tab = VerkaufTab(self)

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.vorabpauschale_tab, "Vorabpauschale")
        self.tabs.addTab(self.freibetrag_tab, "Freibetrag optimieren")
        self.tabs.addTab(self.verkauf_tab, "Verkaufsplanung")

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit – Bitte Datei laden")

    def _setup_menu(self):
        menu_bar = self.menuBar()

        # Datei-Menü
        file_menu = menu_bar.addMenu("&Datei")
        open_action = file_menu.addAction("&Öffnen...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("&Beenden")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)

        # Export-Menü
        export_menu = menu_bar.addMenu("&Export")
        export_vp = export_menu.addAction("Vorabpauschale als CSV...")
        export_vp.triggered.connect(self.vorabpauschale_tab.export_csv)
        export_fb = export_menu.addAction("Freibetrag als CSV...")
        export_fb.triggered.connect(self.freibetrag_tab.export_csv)
        export_vk = export_menu.addAction("Verkaufsplan als CSV...")
        export_vk.triggered.connect(self.verkauf_tab.export_csv)

        # Hilfe-Menü
        help_menu = menu_bar.addMenu("&Hilfe")
        about_action = help_menu.addAction("&Über SteuerPP")
        about_action.triggered.connect(self._show_about)
        disclaimer_action = help_menu.addAction("&Disclaimer")
        disclaimer_action.triggered.connect(self._show_disclaimer)

    def _open_file_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Portfolio Performance Datei öffnen",
            "",
            "PP Dateien (*.xml *.portfolio);;Alle Dateien (*)",
        )
        if filepath:
            self.load_file(filepath)

    def load_file(self, filepath: str):
        try:
            self.portfolio_data = parse_portfolio_file(filepath)
            self.status_bar.showMessage(
                f"Geladen: {Path(filepath).name} – "
                f"{len(self.portfolio_data.securities)} Wertpapiere, "
                f"{len(self.portfolio_data.transactions)} Transaktionen"
            )
            self.dashboard_tab.update_data(self.portfolio_data)
            self.vorabpauschale_tab.update_data(self.portfolio_data)
            self.freibetrag_tab.update_data(self.portfolio_data)
            self.verkauf_tab.update_data(self.portfolio_data)
        except Exception as e:
            QMessageBox.critical(
                self, "Fehler beim Laden", f"Datei konnte nicht geladen werden:\n{e}"
            )

    def _show_disclaimer(self):
        QMessageBox.information(self, "Disclaimer", DISCLAIMER)

    def _show_about(self):
        QMessageBox.about(
            self,
            "Über SteuerPP",
            "SteuerPP v0.1.0\n\n"
            "Steuerrechner für Portfolio Performance\n\n"
            f"{DISCLAIMER}",
        )
