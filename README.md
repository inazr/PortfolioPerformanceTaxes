# SteuerPP – Steuerrechner für Portfolio Performance

Eigenständige Python-Anwendung zur Berechnung deutscher Kapitalertragsteuern auf Basis von Daten aus [Portfolio Performance](https://www.portfolio-performance.info/). Die App liest PP-XML-Dateien ein und berechnet Vorabpauschalen, Freibetrag-Optimierung und Netto-Verkaufsplanung.

> **Disclaimer:** Dieses Tool dient der Orientierung und ersetzt keine Steuerberatung. Alle Berechnungen ohne Gewähr. Bitte konsultieren Sie einen Steuerberater für verbindliche Auskünfte.

## Voraussetzungen

- Python >= 3.13

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install -e ".[dev]"
```

## Starten

### GUI (Standard)

```bash
python -m pptax
```

oder über den installierten Entry Point:

```bash
pptax
```

### GUI mit Datei direkt laden

```bash
pptax --file /pfad/zur/datei.xml
pptax -f /pfad/zur/datei.portfolio
```

### CLI-Modus (ohne GUI)

```bash
pptax --cli-mode --file /pfad/zur/datei.xml
```

### Alle Optionen

| Option | Kurz | Beschreibung |
|---|---|---|
| `--file DATEI` | `-f` | Portfolio Performance XML- oder .portfolio-Datei laden |
| `--cli-mode` | | Textausgabe im Terminal statt GUI |

## Funktionen

- **Dashboard** – Datei laden, Veranlagungstyp/Kirchensteuer/Bundesland konfigurieren, Fondstyp pro Wertpapier zuordnen
- **Vorabpauschale** – Jahresweise Berechnung gem. § 18 InvStG inkl. Teilfreistellung
- **Freibetrag optimieren** – Vorschläge für Verkauf-und-Rückkauf zum Ausnutzen des Sparerpauschbetrags
- **Verkaufsplanung** – „Ich brauche X € netto" – FIFO-konformer Verkaufsplan mit Steuerberechnung
- **CSV-Export** – Alle Ergebnisse als CSV (UTF-8 BOM, deutsches Format)

## Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=pptax
```

## Architektur

Pipeline: **XML-Parser → Datenmodelle → Steuer-Engine → GUI / Export**

```
src/pptax/
├── parser/
│   └── pp_xml_parser.py      PP XStream-XML / .portfolio-ZIP einlesen
├── models/
│   ├── portfolio.py           Security, Transaction, FifoPosition, …
│   └── tax.py                 VorabpauschaleErgebnis, VerkaufsVorschlag, …
├── engine/
│   ├── fifo.py                FIFO-Lostopf je Wertpapier (§ 20 Abs. 4 EStG)
│   ├── vorabpauschale.py      8-Regel-Berechnung (§ 18 InvStG)
│   ├── vp_integration.py      Kumulierte VP je FIFO-Los über mehrere Jahre
│   ├── freibetrag.py          Sparerpauschbetrag-Optimierung
│   ├── verkauf.py             „Ich brauche X € netto"-Verkaufsplaner
│   ├── verlustverrechnung.py  Zwei-Topf-Verlustverrechnung (allg. / Aktien)
│   ├── bestandsschutz.py      Bestandsschutzprüfung (Altbestand vor 2009)
│   ├── tax_params.py          Jahres­parameter aus data/tax_parameters.json
│   └── kurs_utils.py          Nächster-Datum-Kurssuche
├── gui/
│   ├── main_window.py         Hauptfenster, Menü, Status­leiste
│   ├── dashboard_tab.py       Datei laden, Konfiguration, Wertpapier­tabelle
│   ├── vorabpauschale_tab.py  Jahres­weise VP-Berechnung
│   ├── freibetrag_tab.py      Sparerpauschbetrag-Optimierung mit Los-Baum
│   └── verkauf_tab.py         Netto-Verkaufsplanung mit Los-Baum
└── export/
    └── csv_export.py          UTF-8-BOM-CSV im deutschen Zahlenformat
```

Alle Finanzwerte verwenden `Decimal` (niemals `float`).
Steuerparameter sind jahresversionsiert in `data/tax_parameters.json`; der letzte Eintrag für Jahr ≤ Zieljahr gilt.

## Packaging & Releases

Vorkompilierte Binaries für **Windows**, **macOS** und **Linux** werden automatisch per GitHub Actions mit PyInstaller gebaut.

### Binary herunterladen

Fertige Builds stehen unter **Releases** auf GitHub bereit.
Einfach das passende ZIP für das Betriebssystem herunterladen, entpacken und `pptax` ausführen – keine Python-Installation notwendig.

### Release erstellen (Maintainer)

Ein neuer Build wird automatisch gestartet, sobald ein Tag der Form `v*` gepusht wird:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Der Workflow (`.github/workflows/build.yml`) baut auf `windows-latest`, `macos-latest` und `ubuntu-latest` parallel und hängt die ZIPs an das GitHub Release an.

### Lokal mit PyInstaller bauen

```bash
pip install -e ".[dev]"
pyinstaller pptax.spec
# Binary liegt anschließend unter dist/pptax/
```
