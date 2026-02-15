"""Entry Point für SteuerPP (CLI + GUI)."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="pptax",
        description="SteuerPP – Steuerrechner für Portfolio Performance",
    )
    parser.add_argument(
        "--file", "-f", help="Portfolio Performance XML/Portfolio-Datei"
    )
    parser.add_argument(
        "--cli-mode",
        action="store_true",
        help="CLI-Modus (ohne GUI)",
    )
    args = parser.parse_args()

    if args.cli_mode:
        _run_cli(args)
    else:
        _run_gui(args)


def _run_cli(args):
    """Einfacher CLI-Modus."""
    if not args.file:
        print("Fehler: --file ist im CLI-Modus erforderlich.")
        sys.exit(1)

    from pptax.parser.pp_xml_parser import parse_portfolio_file

    data = parse_portfolio_file(args.file)
    print(f"Geladene Wertpapiere: {len(data.securities)}")
    print(f"Transaktionen: {len(data.transactions)}")
    print(f"Historische Kurse: {len(data.kurse)}")
    for sec in data.securities:
        print(f"  - {sec.name} ({sec.isin or 'keine ISIN'})")


def _run_gui(args):
    """Starte die PyQt6-GUI."""
    from PyQt6.QtWidgets import QApplication

    from pptax.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("SteuerPP")
    app.setApplicationVersion("0.1.0")

    window = MainWindow()
    if args.file:
        window.load_file(args.file)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
