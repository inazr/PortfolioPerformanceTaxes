# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SteuerPP is a German capital gains tax calculator for Portfolio Performance portfolio data. It parses PP XML/ZIP files and computes Vorabpauschale, FIFO-based gains, Sparerpauschbetrag optimization, and net sales planning according to German tax law (InvStG, EStG).

Python 3.13+, uses Decimal arithmetic throughout for financial precision.

## Commands

```bash
# Install (editable with dev deps)
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run single test file
pytest tests/test_vorabpauschale.py -v

# Run single test
pytest tests/test_vorabpauschale.py::TestVorabpauschale::test_fall1_normal_positiv -v

# Coverage
pytest tests/ --cov=pptax

# Run app
python -m pptax                              # GUI mode
python -m pptax --cli-mode --file data.xml   # CLI mode
```

## Architecture

Pipeline: **XML Parser → Data Models → Tax Engine → GUI/Export**

- `src/pptax/parser/pp_xml_parser.py` — Parses Portfolio Performance XStream XML format (handles ZIP `.portfolio` files, cross-references via XStream `reference` attributes, PP integer encoding: ÷100 for money, ÷10^8 for shares)
- `src/pptax/models/` — Dataclasses: `Security`, `Transaction`, `FifoPosition`, `VorabpauschaleErgebnis`, `VerkaufsVorschlag`, etc.
- `src/pptax/engine/` — Stateless calculation modules:
  - `fifo.py` — FIFO lot queue per security (§20 Abs. 4 Satz 7 EStG)
  - `vorabpauschale.py` — 8-rule Vorabpauschale calc (§18 InvStG)
  - `vp_integration.py` — Multi-year cumulative VP per FIFO lot
  - `freibetrag.py` — Sparerpauschbetrag optimization (suggests sales to use annual allowance)
  - `verkauf.py` — "I need X€ net" sales planner
  - `verlustverrechnung.py` — Two-bucket loss carryforward (general vs. stock-specific)
  - `tax_params.py` — Year-based parameter lookup from `data/tax_parameters.json`
  - `kurs_utils.py` — Nearest-date price lookup
- `src/pptax/gui/` — PyQt6 tabbed interface (Dashboard, Vorabpauschale, Freibetrag, Verkaufsplanung)
- `src/pptax/export/csv_export.py` — UTF-8 BOM CSV with German number format

## Key Conventions

- All financial values use `Decimal`, never `float`
- Tax parameters are year-versioned in `tax_parameters.json` — lookup returns the last valid entry for year ≤ target
- Fund types (`FondsTyp` enum) determine partial exemption rates (Teilfreistellung): Aktienfonds 30%, Mischfonds 15%, Immobilienfonds 60%/80%, Sonstige 0%
- Transaction types: KAUF, VERKAUF, EINLIEFERUNG, AUSLIEFERUNG, DIVIDENDE
- Test fixtures in `tests/conftest.py` provide sample securities and transactions
- `tests/test_data/sample_portfolio.xml` contains a multi-security test portfolio
- GUI formatting uses German locale: `1.234,56 €`, `DD.MM.YYYY`, comma decimal separator


## Key Coding Principles

- YASNI
- KISS
- DRY
- SOLID
- SSOT

## Key Claude Rules

- Use up to 6 Explore Agents
- *IMPORTANT*: DO NOT ASSUME ANYTHING! Ask many clarification questions! 
- Use context7 if needed
- Use skills if available
- Failure is an option. It is better to stop and ask for help then to create something with flaws.
