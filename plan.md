# SteuerPP – Implementierungsplan

## Projektübersicht

**Name:** SteuerPP – Steuerrechner für Portfolio Performance  
**Sprache:** Python 3.11+  
**Plattform:** Plattformunabhängig (Windows, macOS, Linux)  
**Lizenz:** MIT  

Eigenständige Python-Anwendung zur Berechnung deutscher Kapitalertragsteuern auf Basis von Daten aus [Portfolio Performance](https://www.portfolio-performance.info/). Die App liest PP-XML-Dateien ein und berechnet Vorabpauschalen, Freibetrag-Optimierung und Netto-Verkaufsplanung.

---

## Architektur

```
Portfolio Performance .xml/.portfolio Datei
         ↓
    XML-Parser (lxml / eigener Parser)
         ↓
    Interne Datenmodelle (dataclasses)
         ↓
    Steuer-Engine (Berechnungslogik)
         ↓
    GUI (PyQt6) + CLI-Modus
```

### Projektstruktur

```
steuer-pp/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── steuer_pp/
│       ├── __init__.py
│       ├── __main__.py              # Entry Point (CLI + GUI)
│       ├── config.py                # App-Konfiguration
│       │
│       ├── data/
│       │   └── tax_parameters.json  # Historische Steuerparameter
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── portfolio.py         # Datenmodelle: Security, Transaction, Position
│       │   └── tax.py               # Datenmodelle: TaxResult, Vorabpauschale etc.
│       │
│       ├── parser/
│       │   ├── __init__.py
│       │   └── pp_xml_parser.py     # PP XML Datei einlesen
│       │
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── tax_params.py        # Historische Parameter-Lookup-Logik
│       │   ├── fifo.py              # FIFO-Bestandsführung
│       │   ├── vorabpauschale.py    # Vorabpauschale-Berechnung
│       │   ├── freibetrag.py        # Sparerpauschbetrag-Optimierung
│       │   ├── verkauf.py           # Netto-Verkaufsplanung
│       │   └── verlustverrechnung.py # Verlustverrechnungstöpfe
│       │
│       ├── gui/
│       │   ├── __init__.py
│       │   ├── main_window.py
│       │   ├── dashboard_tab.py
│       │   ├── vorabpauschale_tab.py
│       │   ├── freibetrag_tab.py
│       │   └── verkauf_tab.py
│       │
│       └── export/
│           ├── __init__.py
│           └── csv_export.py        # Export der Ergebnisse
│
└── tests/
    ├── __init__.py
    ├── conftest.py                  # Shared Fixtures
    ├── test_tax_params.py
    ├── test_fifo.py
    ├── test_vorabpauschale.py
    ├── test_freibetrag.py
    ├── test_verkauf.py
    └── test_data/
        └── sample_portfolio.xml     # Testdaten (minimale PP-XML)
```

---

## Historische Steuerparameter

### KRITISCH: Alle Berechnungen müssen jahresabhängig sein!

Keine Steuerparameter dürfen als Konstanten hardcoded werden. Alle Werte werden über eine zentrale Lookup-Funktion abgerufen, die den letzten gültigen Wert für ein gegebenes Jahr zurückgibt.

### Datei: `src/steuer_pp/data/tax_parameters.json`

```json
{
  "_meta": {
    "description": "Historische deutsche Steuerparameter für Investmentfonds. Jeder Eintrag gilt ab dem angegebenen Jahr bis ein neuer Eintrag folgt.",
    "last_updated": "2026-02-15",
    "sources": [
      "BMF-Schreiben § 18 Abs. 4 InvStG",
      "§ 20 InvStG (Teilfreistellungen)",
      "§ 32d EStG (Abgeltungssteuer)",
      "§ 20 Abs. 9 EStG (Sparer-Pauschbetrag)"
    ]
  },
  "basiszins_vorabpauschale": {
    "_comment": "Basiszins gem. § 18 Abs. 4 InvStG, veröffentlicht vom BMF. Quelle: Deutsche Bundesbank Zinsstrukturdaten, jeweils zum 2. Januar des Jahres.",
    "2018": 0.0087,
    "2019": 0.0052,
    "2020": 0.0007,
    "2021": -0.0045,
    "2022": -0.0005,
    "2023": 0.0255,
    "2024": 0.0229,
    "2025": 0.0253,
    "2026": 0.0320
  },
  "sparerpauschbetrag": {
    "_comment": "Jährlicher Freibetrag für Kapitalerträge gem. § 20 Abs. 9 EStG.",
    "2009": { "single": 801, "joint": 1602 },
    "2023": { "single": 1000, "joint": 2000 }
  },
  "abgeltungssteuer_satz": {
    "_comment": "Kapitalertragsteuersatz gem. § 32d EStG.",
    "2009": 0.25
  },
  "solidaritaetszuschlag_satz": {
    "_comment": "Solidaritätszuschlag auf die Abgeltungssteuer (5,5% der KESt).",
    "2009": 0.055
  },
  "kirchensteuer_saetze": {
    "_comment": "Kirchensteuersatz je Bundesland, auf die KESt. Optional, nur wenn Nutzer Kirchensteuer aktiviert.",
    "2009": {
      "bayern": 0.08,
      "baden_wuerttemberg": 0.08,
      "default": 0.09
    }
  },
  "teilfreistellung": {
    "_comment": "Teilfreistellungssätze gem. § 20 InvStG. Seit Einführung 2018 unverändert. Aktienfonds: mind. 51% Aktienquote. Mischfonds: mind. 25% Aktienquote. Immobilienfonds Inland: fortlaufend mind. 51% Immobilien in DE. Immobilienfonds Ausland: fortlaufend mind. 51% Immobilien in Ausland.",
    "2018": {
      "aktienfonds": 0.30,
      "mischfonds": 0.15,
      "immobilienfonds_inland": 0.60,
      "immobilienfonds_ausland": 0.80,
      "sonstige": 0.00
    }
  },
  "vorabpauschale_faktor": {
    "_comment": "Faktor zur Berechnung des Basisertrags: Basisertrag = Wert_Jahresanfang × Basiszins × Faktor. Gem. § 18 Abs. 1 InvStG.",
    "2018": 0.70
  }
}
```

### Lookup-Logik: `src/steuer_pp/engine/tax_params.py`

```python
"""
Zentrale Lookup-Funktion für historische Steuerparameter.

Prinzip: Jeder Eintrag in tax_parameters.json gilt ab dem angegebenen Jahr
bis ein neuerer Eintrag ihn überschreibt. Die Funktion sucht den letzten
gültigen Wert <= dem angefragten Jahr.

Beispiel:
    sparerpauschbetrag hat Einträge für 2009 und 2023.
    - get_param("sparerpauschbetrag", 2022) → {"single": 801, "joint": 1602}
    - get_param("sparerpauschbetrag", 2023) → {"single": 1000, "joint": 2000}
    - get_param("sparerpauschbetrag", 2025) → {"single": 1000, "joint": 2000}
"""
```

Die Funktion `get_param(param_name: str, year: int)` muss:
1. Die JSON-Datei laden (mit Caching, nur einmal pro Laufzeit)
2. Alle Jahreszahlen-Keys für den Parameter sortieren
3. Den letzten Key finden der `<= year` ist
4. Den zugehörigen Wert zurückgeben
5. Einen `ValueError` werfen wenn kein gültiger Eintrag existiert (z.B. `basiszins_vorabpauschale` vor 2018)

Zusätzlich eine Hilfsfunktion:

```python
def get_gesamtsteuersatz(year: int, kirchensteuer: bool = False, 
                         bundesland: str = "default") -> float:
    """
    Berechnet den kombinierten Steuersatz.
    
    Ohne Kirchensteuer: KESt + Soli auf KESt
      = 0.25 + 0.25 * 0.055 = 0.26375
      
    Mit Kirchensteuer: Sonderberechnung gem. § 32d Abs. 1 Satz 3 EStG
      KESt_eff = (4 + kirchensteuersatz) / (4 + kirchensteuersatz) ... 
      (vereinfacht: KESt wird um Kirchensteuer-Faktor gemindert)
    
    Die exakte Formel MIT Kirchensteuer:
      e = Abgeltungssteuersatz (0.25)
      s = Soli-Satz (0.055)  
      k = Kirchensteuersatz (0.08 oder 0.09)
      
      KESt_effektiv = e / (1 + k * e)  → z.B. 0.25 / 1.0225 ≈ 0.24451 bei k=0.09
      Soli = KESt_effektiv * s
      KiSt = KESt_effektiv * k
      Gesamtsatz = KESt_effektiv + Soli + KiSt
    """
```

---

## Datenmodelle

### Datei: `src/steuer_pp/models/portfolio.py`

```python
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

class FondsTyp(Enum):
    """Fondstyp für Teilfreistellungsermittlung."""
    AKTIENFONDS = "aktienfonds"
    MISCHFONDS = "mischfonds"
    IMMOBILIENFONDS_INLAND = "immobilienfonds_inland"
    IMMOBILIENFONDS_AUSLAND = "immobilienfonds_ausland"
    SONSTIGE = "sonstige"

class TransaktionsTyp(Enum):
    KAUF = "kauf"
    VERKAUF = "verkauf"
    EINLIEFERUNG = "einlieferung"  # Depotübertrag
    AUSLIEFERUNG = "auslieferung"
    DIVIDENDE = "dividende"

@dataclass
class Security:
    """Ein Wertpapier / ETF / Fonds."""
    uuid: str                           # PP-interne UUID
    name: str
    isin: Optional[str] = None
    wkn: Optional[str] = None
    fonds_typ: FondsTyp = FondsTyp.AKTIENFONDS  # Muss vom User gesetzt werden
    is_fond: bool = True                # Fällt unter InvStG 2018?

@dataclass
class Transaction:
    """Eine einzelne Transaktion."""
    datum: date
    typ: TransaktionsTyp
    security_uuid: str
    stuecke: Decimal
    kurs: Decimal                        # Kurs pro Stück
    gesamtbetrag: Decimal               # Gesamtbetrag inkl. Gebühren
    gebuehren: Decimal = Decimal("0")
    steuern: Decimal = Decimal("0")      # Bereits gezahlte Steuern (z.B. Quellensteuer)

@dataclass
class HistorischerKurs:
    """Kurs zu einem Stichtag (z.B. 1.1. und 31.12.)."""
    security_uuid: str
    datum: date
    kurs: Decimal

@dataclass
class FifoPosition:
    """Eine einzelne FIFO-Position (ein Kauflot)."""
    kaufdatum: date
    stuecke: Decimal
    einstandskurs: Decimal               # Kaufkurs pro Stück
    security_uuid: str
    # Summe bereits angesetzter Vorabpauschalen für dieses Lot
    vorabpauschalen_kumuliert: Decimal = Decimal("0")
```

### Datei: `src/steuer_pp/models/tax.py`

```python
@dataclass
class VorabpauschaleErgebnis:
    """Ergebnis der Vorabpauschale-Berechnung für ein Wertpapier und ein Jahr."""
    security_uuid: str
    jahr: int
    wert_jahresanfang: Decimal
    wert_jahresende: Decimal
    basiszins: Decimal
    basisertrag: Decimal
    wertsteigerung: Decimal
    ausschuettungen: Decimal             # Bereits erhaltene Ausschüttungen im Jahr
    vorabpauschale_brutto: Decimal       # Vor Teilfreistellung
    teilfreistellung_satz: Decimal
    vorabpauschale_steuerpflichtig: Decimal  # Nach Teilfreistellung
    steuer: Decimal                      # Tatsächlich zu zahlende Steuer

@dataclass
class FreibetragOptimierungErgebnis:
    """Empfehlung zum Ausnutzen des Sparerpauschbetrags."""
    jahr: int
    freibetrag_gesamt: Decimal
    freibetrag_bereits_genutzt: Decimal
    freibetrag_verbleibend: Decimal
    verkaufsempfehlungen: list           # Liste von Verkaufsvorschlägen

@dataclass
class VerkaufsVorschlag:
    """Ein konkreter Verkaufsvorschlag."""
    security_uuid: str
    security_name: str
    isin: str
    stuecke: Decimal
    kaufdatum: date                      # FIFO: ältestes Lot
    einstandskurs: Decimal
    aktueller_kurs: Decimal
    brutto_erloes: Decimal
    gewinn_brutto: Decimal
    teilfreistellung_satz: Decimal
    gewinn_steuerpflichtig: Decimal
    steuer: Decimal
    netto_erloes: Decimal

@dataclass
class NettoBetragPlan:
    """Verkaufsplan um einen Netto-Zielbetrag zu erhalten."""
    ziel_netto: Decimal
    erreichtes_netto: Decimal
    brutto_gesamt: Decimal
    steuer_gesamt: Decimal
    freibetrag_genutzt: Decimal
    verkaufsplan: list[VerkaufsVorschlag]
```

---

## Kernlogik

### 1. PP XML Parser (`src/steuer_pp/parser/pp_xml_parser.py`)

Portfolio Performance speichert Daten als XML (XStream-Serialisierung). Die Datei kann auch als `.portfolio` vorliegen (dann ist sie ZIP-komprimiert mit der XML darin).

**Zu extrahierende Daten:**
- `/client/securities/*` → Security-Objekte (Name, ISIN, WKN, UUID)
- `/client/accounts/*/transactions/*` → Dividenden, Zinsen
- `/client/portfolios/*/transactions/*` → Käufe, Verkäufe
- `/client/securities/*/prices/*` → Historische Kurse (für Jahresanfang/-ende Werte)

**Hinweise:**
- PP nutzt XStream-Referenzen (`reference="../../.."`), die aufgelöst werden müssen
- UUIDs verknüpfen Securities mit Transactions
- Kurse sind in Centbeträgen (integer) gespeichert → Division durch 10^x nötig (PP speichert typischerweise in der kleinsten Einheit)
- `.portfolio`-Dateien: Erst entpacken (`zipfile`), dann XML parsen
- Es gibt auch ein neueres Format mit `id`-Attributen (seit PP 0.70.3), das einfacher zu parsen ist

**Empfehlung:** Nutze `lxml` für XPath-Queries. Studiere eine echte PP-XML-Datei um die exakte Struktur zu verstehen. Das Tool [ppxml2db](https://github.com/pfalcon/ppxml2db) kann als Referenz dienen, muss aber nicht als Dependency eingebunden werden.

### 2. FIFO-Bestandsführung (`src/steuer_pp/engine/fifo.py`)

Die FIFO-Logik (First In, First Out) ist fundamental für die korrekte Gewinnermittlung bei Verkäufen. In Deutschland gilt für Privatanleger FIFO gem. § 20 Abs. 4 Satz 7 EStG.

```python
class FifoBestand:
    """
    Verwaltet FIFO-Bestände für ein einzelnes Wertpapier.
    
    Methoden:
    - kauf(datum, stuecke, kurs): Fügt ein neues Lot hinzu
    - verkauf(datum, stuecke, aktueller_kurs) -> list[VerkauftePosition]:
        Verkauft FIFO-konform und gibt die verkauften Lots mit Gewinn zurück
    - bestand() -> list[FifoPosition]: Aktueller Bestand aller offenen Lots
    - gewinn_bei_verkauf(stuecke, aktueller_kurs) -> Decimal:
        Simuliert Verkauf ohne Bestand zu verändern (für Planung)
    """
```

**Wichtig bei Verkäufen:**
- Gewinn = (Verkaufskurs - Einstandskurs) × Stücke
- Beim Verkauf: kumulierte Vorabpauschalen des Lots vom Gewinn abziehen (§ 19 Abs. 1 Satz 3 InvStG), da diese bereits versteuert wurden
- Ein Lot kann teilweise verkauft werden (dann bleibt der Rest als eigenes Lot erhalten)

### 3. Vorabpauschale (`src/steuer_pp/engine/vorabpauschale.py`)

```
Rechtsgrundlage: § 18 InvStG

Berechnung für ein Wertpapier und ein Steuerjahr:

1. Basisertrag = Wert_1.Januar × Basiszins(Jahr) × 0,7
2. Wertsteigerung = Wert_31.Dezember - Wert_1.Januar
3. Wenn Wertsteigerung <= 0: Vorabpauschale = 0 (keine Besteuerung bei Verlusten)
4. Vorabpauschale_brutto = min(Basisertrag, Wertsteigerung)
5. Vorabpauschale_brutto -= Ausschüttungen_des_Jahres  (nicht negativ!)
6. Vorabpauschale_brutto = max(0, Vorabpauschale_brutto)
7. Steuerpflichtig = Vorabpauschale_brutto × (1 - Teilfreistellungssatz)
8. Steuer = Steuerpflichtig × Gesamtsteuersatz(Jahr)

Sonderregeln:
- Bei unterjährigem Kauf: Vorabpauschale × (12 - volle_Monate_vor_Kauf) / 12
  (§ 18 Abs. 2 InvStG)
- Wenn Basiszins negativ (2021, 2022): Vorabpauschale = 0
- Die Vorabpauschale gilt als zugeflossen am 1. Werktag des FOLGEJAHRES
  (§ 18 Abs. 3 InvStG)
- Vorabpauschalen werden auf dem FIFO-Lot kumuliert und bei Verkauf angerechnet
```

**Alle Parameter (Basiszins, Teilfreistellung, Steuersatz) über `tax_params.get_param(name, jahr)` laden!**

### 4. Freibetrag-Optimierung (`src/steuer_pp/engine/freibetrag.py`)

```
Ziel: Berechne optimale Verkäufe um den Sparerpauschbetrag maximal auszunutzen.

Strategie "Verkauf und sofortiger Rückkauf" (Tax-Loss/Gain Harvesting):
- Verkaufe Anteile mit Gewinn, um Freibetrag auszuschöpfen
- Kaufe sie sofort wieder (neuer, höherer Einstandskurs)
- Steuer: 0 € (innerhalb Freibetrag)
- Effekt: Einstandskurs wird angehoben → weniger Steuern bei späterem "echtem" Verkauf

Algorithmus:
1. Freibetrag_verbleibend = Sparerpauschbetrag(Jahr) - bereits_genutzt
   (bereits_genutzt = Summe aller steuerpflichtigen Kapitalerträge des Jahres:
    Dividenden, Zinsen, realisierte Gewinne, Vorabpauschalen)
2. Für jede Position berechne den steuerpflichtigen Gewinn pro Stück
   (nach Teilfreistellung)
3. Sortiere Positionen nach Gewinn pro Stück absteigend (effizienteste zuerst)
4. Berechne wie viele Stücke pro Position verkauft werden müssen um den
   Freibetrag möglichst genau auszuschöpfen
5. Beachte: FIFO! Es werden die ältesten Lots zuerst verkauft
6. Berücksichtige Transaktionskosten (Spread etc.) als optionalen Parameter

Eingabe:
- jahr: int
- veranlagungstyp: "single" | "joint"
- bereits_genutzt: Decimal (Summe bisheriger steuerpflichtiger Erträge)
- positionen: alle aktuellen Bestände mit FIFO-Lots
- aktuelle_kurse: Dict[security_uuid, Decimal]

Ausgabe:
- FreibetragOptimierungErgebnis mit konkreten Verkaufsvorschlägen
```

### 5. Netto-Verkaufsplanung (`src/steuer_pp/engine/verkauf.py`)

```
Ziel: "Ich brauche X € netto – wie viel muss ich verkaufen?"

Algorithmus:
1. Ermittle Gesamtsteuersatz für das Jahr
2. Ermittle verbleibenden Freibetrag
3. Sortiere FIFO-Lots nach Kaufdatum (FIFO-Prinzip)
4. Iteriere über Lots:
   a. Berechne Gewinn pro Stück = aktueller_kurs - einstandskurs - vorabpauschalen_kumuliert
   b. Steuerpflichtiger Gewinn = Gewinn × (1 - Teilfreistellung)
   c. Wenn Freibetrag verbleibend > 0:
      - Gewinn_frei = min(steuerpflichtiger_gewinn_pro_stueck, freibetrag_verbleibend / stuecke)
      - Steuer_pro_stueck auf den Teil berechnen, der über dem Freibetrag liegt
   d. Netto_pro_stueck = aktueller_kurs - steuer_pro_stueck
   e. Berechne benötigte Stücke: ceil(noch_benötigt / netto_pro_stueck)
   f. Begrenze auf verfügbare Stücke im Lot
5. Wiederhole bis Ziel-Netto erreicht oder keine Bestände mehr
6. Berücksichtige: Bei Verlust-Positionen ist Netto > Brutto möglich
   (Verlustverrechnung reduziert Steuerlast anderer Gewinne)

Eingabe:
- ziel_netto: Decimal
- jahr: int
- veranlagungstyp: "single" | "joint"
- freibetrag_bereits_genutzt: Decimal
- positionen: alle aktuellen Bestände mit FIFO-Lots
- aktuelle_kurse: Dict[security_uuid, Decimal]
- kirchensteuer: bool (optional)
- bundesland: str (optional)

Ausgabe:
- NettoBetragPlan mit detailliertem Verkaufsplan
```

### 6. Verlustverrechnung (`src/steuer_pp/engine/verlustverrechnung.py`)

```
Verlustverrechnungstöpfe gem. deutschem Steuerrecht:

Topf 1: Allgemeiner Verlustverrechnungstopf (Kapitalerträge)
  - Verluste aus Fondsverkäufen
  - Verrechnung mit: allen positiven Kapitalerträgen (Gewinne, Dividenden, Vorabpauschalen)
  
Topf 2: Aktien-Verlustverrechnungstopf (NUR Einzelaktien, NICHT Fonds/ETFs!)
  - Verluste aus Einzelaktienverkäufen
  - Verrechnung NUR mit: Gewinnen aus Einzelaktienverkäufen
  - Nicht verrechenbar mit Dividenden, Fondsgewinnen etc.
  - HINWEIS: Dieses Programm fokussiert auf Fonds/ETFs, daher ist Topf 2 
    nur informativ relevant

Sonderregel Termingeschäfte (§ 20 Abs. 6 Satz 5 EStG):
  - Nicht im Scope dieses Programms

Die Verlustverrechnung erfolgt VOR dem Sparerpauschbetrag.
Nicht verrechnete Verluste werden ins Folgejahr vorgetragen.
```

---

## GUI-Spezifikation (PyQt6)

### Hauptfenster mit Tabs

**Tab 1: Dashboard / Übersicht**
- Datei laden (PP XML)
- Zusammenfassung: Anzahl Wertpapiere, Gesamtwert, unrealisierte Gewinne
- Konfiguration: Veranlagungstyp (Single/Joint), Kirchensteuer ja/nein, Bundesland
- Bereits genutzter Freibetrag (manuell eingebbar, da nicht aus PP ableitbar)

**Tab 2: Vorabpauschale**
- Jahresauswahl (Dropdown)
- Tabelle: Wertpapier | ISIN | Wert 1.1. | Wert 31.12. | Basisertrag | Vorabpauschale | Teilfreistellung | Steuerpflichtig | Steuer
- Summenzeile
- Hinweis wenn Basiszins negativ (keine Vorabpauschale)
- Historische Ansicht: Vorabpauschalen über mehrere Jahre

**Tab 3: Freibetrag optimieren**
- Anzeige: Freibetrag gesamt / bereits genutzt / verbleibend
- Eingabefeld: Bereits genutzter Freibetrag (€)
- Button: "Optimale Verkäufe berechnen"
- Ergebnis-Tabelle: Wertpapier | ISIN | Stücke | Gewinn | Steuer (0€) | Effekt
- Hinweis: "Verkauf und sofortiger Rückkauf zum neuen Einstandskurs"

**Tab 4: Verkaufsplanung**
- Eingabefeld: "Ich brauche X € netto"
- Button: "Berechnen"
- Ergebnis: Brutto-Erlös | Steuer | Netto-Erlös
- Detail-Tabelle: Wertpapier | ISIN | Stücke | Kauf am | Einstand | Aktuell | Gewinn | Steuer | Netto
- FIFO-Kennzeichnung pro Lot

### GUI-Richtlinien
- Alle Beträge mit 2 Nachkommastellen und € Zeichen formatieren
- Prozentwerte mit 2 Nachkommastellen und % Zeichen
- Datumsformat: DD.MM.YYYY
- Negative Werte in Rot darstellen
- Responsive Layout mit sinnvollen Mindestgrößen

---

## Dependencies

### `pyproject.toml`

```toml
[project]
name = "steuer-pp"
version = "0.1.0"
description = "Steuerrechner für Portfolio Performance"
requires-python = ">=3.11"
dependencies = [
    "lxml>=5.0",
    "PyQt6>=6.5",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[project.scripts]
steuer-pp = "steuer_pp.__main__:main"
```

**Bewusst minimale Dependencies:**
- `lxml` für XML-Parsing (performant, XPath-Support)
- `PyQt6` für GUI
- Python `decimal.Decimal` für alle Geldbeträge (KEIN float!)
- Python `dataclasses` für Modelle
- Python `json` für tax_parameters.json
- Python `zipfile` für .portfolio-Dateien

---

## Tests

### Teststrategie

Jede Engine-Komponente muss Unit-Tests haben. Teste insbesondere Grenzfälle:

### `tests/test_tax_params.py`
- Lookup für existierendes Jahr (exakt)
- Lookup für Jahr zwischen zwei Einträgen (letzter gültiger)
- Lookup für Jahr nach dem letzten Eintrag
- Lookup für Jahr vor dem ersten Eintrag → ValueError
- Basiszins-Werte gegen BMF-Quellen prüfen

### `tests/test_vorabpauschale.py`
```python
# Testfälle mit erwarteten Ergebnissen:

# Fall 1: Normaler positiver Basiszins, Wertsteigerung > Basisertrag
# Jahr 2023, Basiszins 2.55%, Aktienfonds (TFS 30%)
# Wert 1.1.: 10.000€, Wert 31.12.: 12.000€, keine Ausschüttungen
# Basisertrag = 10000 × 0.0255 × 0.7 = 178.50
# Wertsteigerung = 2000 > 178.50 → Vorabpauschale = 178.50
# Steuerpflichtig = 178.50 × 0.70 = 124.95
# Steuer = 124.95 × 0.26375 = 32.96

# Fall 2: Wertsteigerung < Basisertrag
# Wert 1.1.: 10.000€, Wert 31.12.: 10.100€
# Basisertrag = 178.50, Wertsteigerung = 100 → Vorabpauschale = 100.00

# Fall 3: Negativer Basiszins (2021)
# → Vorabpauschale = 0, Steuer = 0

# Fall 4: Wertverlust
# Wert 31.12. < Wert 1.1. → Vorabpauschale = 0

# Fall 5: Mit Ausschüttungen
# Ausschüttungen >= Basisertrag → Vorabpauschale = 0
# Ausschüttungen < Basisertrag → Vorabpauschale = Basisertrag - Ausschüttungen

# Fall 6: Unterjähriger Kauf (§ 18 Abs. 2 InvStG)
# Kauf im März → nur 10/12 der Vorabpauschale

# Fall 7: Verschiedene Fondstypen (unterschiedliche Teilfreistellungen)
```

### `tests/test_fifo.py`
- Einfacher Kauf/Verkauf
- Teilverkauf eines Lots
- Mehrere Lots, FIFO-Reihenfolge verifizieren
- Verkauf über mehrere Lots hinweg
- Vorabpauschalen-Anrechnung bei Verkauf

### `tests/test_freibetrag.py`
- Freibetrag vollständig ausschöpfen
- Freibetrag teilweise bereits genutzt
- Keine Gewinne vorhanden (kein Verkauf nötig)
- Gewinne reichen nicht um Freibetrag auszuschöpfen
- Verschiedene Teilfreistellungssätze

### `tests/test_verkauf.py`
- Einfacher Verkauf ohne Freibetrag
- Verkauf mit teilweisem Freibetrag
- Verkauf über mehrere FIFO-Lots
- Verlust-Position (negative Steuer)
- Zielbetrag nicht erreichbar (nicht genug Bestand)

---

## Implementierungsreihenfolge

### Phase 1: Fundament
1. `tax_parameters.json` anlegen mit allen historischen Werten
2. `tax_params.py` implementieren mit Tests
3. `models/portfolio.py` und `models/tax.py` definieren
4. `fifo.py` implementieren mit Tests

### Phase 2: Engine
5. `vorabpauschale.py` implementieren mit Tests
6. `freibetrag.py` implementieren mit Tests
7. `verkauf.py` implementieren mit Tests
8. `verlustverrechnung.py` (Basis-Version) implementieren

### Phase 3: Parser
9. `pp_xml_parser.py` implementieren
10. Mit echter PP-Datei testen und Kantenabdeckung sicherstellen
11. ZIP/Portfolio-Datei-Support

### Phase 4: GUI
12. Hauptfenster mit Tab-Struktur
13. Dashboard-Tab (Datei laden, Konfiguration)
14. Vorabpauschale-Tab
15. Freibetrag-Tab
16. Verkaufsplanung-Tab

### Phase 5: Polish
17. CSV-Export
18. Fehlerbehandlung und Validierung
19. README.md und Benutzerdokumentation
20. PyInstaller-Konfiguration für Standalone-Executable

---

## Wichtige Implementierungshinweise

### Decimal, nicht Float!
Alle Geldbeträge und Prozentsätze als `decimal.Decimal` speichern und berechnen. Niemals `float` für Finanzmathematik verwenden.

```python
from decimal import Decimal, ROUND_HALF_UP

# Richtig:
betrag = Decimal("10000.00")
satz = Decimal("0.26375")
steuer = (betrag * satz).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# FALSCH:
steuer = 10000.0 * 0.26375  # Floating-Point-Fehler!
```

### Steuerjahr vs. Zufluss
Die Vorabpauschale für ein Steuerjahr gilt als zugeflossen am 1. Werktag des FOLGEJAHRES. Das bedeutet:
- Basiszins von 2025 → Vorabpauschale wird Anfang 2026 belastet
- Belastet den Sparerpauschbetrag von 2026, nicht 2025!

### Fondstyp ist nicht automatisch ermittelbar
Der Fondstyp (Aktien/Misch/Immobilien/Sonstige) bestimmt die Teilfreistellung, ist aber NICHT in der PP-XML-Datei enthalten. Der User muss den Fondstyp pro Wertpapier manuell zuordnen. Die GUI braucht dafür ein Mapping (z.B. als eigene JSON-Konfigdatei).

### Bereits genutzter Freibetrag
PP kennt keine Freibeträge. Der User muss den bereits genutzten Betrag manuell eingeben (z.B. von Tagesgeld-Zinsen bei einer anderen Bank, Dividenden anderer Broker etc.).

### Kirchensteuer ist optional
Standardmäßig ohne Kirchensteuer berechnen. Wenn aktiviert, ändert sich nicht nur die Steuer, sondern auch der effektive KESt-Satz (Herabsetzung der KESt bei Kirchensteuerpflicht gem. § 32d Abs. 1 Satz 3 EStG).

### Disclaimer
Die Anwendung muss beim Start und in der Info-Seite einen Disclaimer anzeigen:
"Dieses Tool dient der Orientierung und ersetzt keine Steuerberatung. Alle Berechnungen ohne Gewähr. Bitte konsultieren Sie einen Steuerberater für verbindliche Auskünfte."