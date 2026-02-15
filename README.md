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
