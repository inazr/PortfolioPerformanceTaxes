"""PP XML Datei einlesen.

Parst Portfolio Performance XML-Dateien (.xml und .portfolio ZIP).
Unterstützt XStream id/reference Auflösung.
Konvertiert PP Integer-Beträge zu Decimal (÷100 für Geld, ÷10^8 für Anteile).
"""

import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from lxml import etree

from pptax.models.portfolio import (
    Security,
    Transaction,
    TransaktionsTyp,
    HistorischerKurs,
    FondsTyp,
    PortfolioData,
    PortfolioInfo,
)


# PP speichert Geldbeträge als Centbeträge (integer ÷ 100)
MONEY_DIVISOR = Decimal("100")
# PP speichert Anteile als integer ÷ 10^8
SHARES_DIVISOR = Decimal("100000000")


def _to_money(value: str | int) -> Decimal:
    """Konvertiere PP-Integer-Betrag zu Decimal."""
    return Decimal(str(value)) / MONEY_DIVISOR


def _to_shares(value: str | int) -> Decimal:
    """Konvertiere PP-Integer-Anteile zu Decimal."""
    return Decimal(str(value)) / SHARES_DIVISOR


def _parse_date(date_str: str) -> date:
    """Parst ein Datum aus PP-XML. Unterstützt ISO und PP-Format."""
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unbekanntes Datumsformat: {date_str}")


def _resolve_reference(elem: etree._Element) -> etree._Element | None:
    """Löst ein einzelnes XStream reference-Attribut auf.

    XStream serialisiert Objekte einmal vollständig und referenziert
    sie danach mit relativen XPath-Pfaden im reference-Attribut.
    Gibt das Ziel-Element zurück oder None.
    """
    ref = elem.get("reference")
    if ref is None:
        return None
    try:
        target = elem.xpath(ref)
        if target:
            return target[0] if isinstance(target, list) else target
    except Exception:
        pass
    return None


def _extract_securities(root: etree._Element) -> list[Security]:
    """Extrahiere Wertpapiere aus der XML-Struktur."""
    securities = []
    for sec_elem in root.xpath("//client/securities/security"):
        uuid = _get_text(sec_elem, "uuid", "")
        name = _get_text(sec_elem, "name", "Unbekannt")
        isin = _get_text(sec_elem, "isin")
        wkn = _get_text(sec_elem, "wkn")

        if uuid:
            securities.append(
                Security(uuid=uuid, name=name, isin=isin, wkn=wkn)
            )
    return securities


def _extract_portfolios(root: etree._Element) -> list[PortfolioInfo]:
    """Extrahiere Portfolio/Depot-Metadaten."""
    portfolios = []
    for ptf_elem in root.xpath("//client/portfolios/portfolio"):
        uuid = _get_text(ptf_elem, "uuid", "")
        name = _get_text(ptf_elem, "name", "Unbekannt")
        if not uuid:
            continue

        # referenceAccount UUID auflösen
        ref_acc_uuid = None
        ref_acc_elem = ptf_elem.find("referenceAccount")
        if ref_acc_elem is not None:
            target = _resolve_reference(ref_acc_elem)
            if target is not None:
                ref_acc_uuid = _get_text(target, "uuid")
            else:
                ref_acc_uuid = _get_text(ref_acc_elem, "uuid")

        portfolios.append(
            PortfolioInfo(
                uuid=uuid, name=name, reference_account_uuid=ref_acc_uuid
            )
        )
    return portfolios


def _extract_transactions(
    root: etree._Element,
    portfolios: list[PortfolioInfo] | None = None,
) -> list[Transaction]:
    """Extrahiere Transaktionen aus Portfolio- und Kontotransaktionen."""
    transactions = []
    seen_uuids: set[str] = set()
    # Halte Referenzen auf verarbeitete lxml-Elemente (verhindert Proxy-GC)
    seen_elems: list[etree._Element] = []

    # Account-UUID → Portfolio-UUID Mapping (für Dividenden)
    account_to_portfolio: dict[str, str] = {}
    if portfolios:
        for ptf in portfolios:
            if ptf.reference_account_uuid:
                account_to_portfolio[ptf.reference_account_uuid] = ptf.uuid

    # Portfolio-Transaktionen — per Portfolio iterieren für portfolio_uuid
    for ptf_elem in root.xpath("//client/portfolios/portfolio"):
        ptf_uuid = _get_text(ptf_elem, "uuid")
        for tx_elem in ptf_elem.xpath(".//portfolio-transaction"):
            uuid = _get_text(tx_elem, "uuid")
            if uuid and uuid in seen_uuids:
                continue
            if uuid:
                seen_uuids.add(uuid)
            seen_elems.append(tx_elem)
            tx = _parse_portfolio_transaction(tx_elem, portfolio_uuid=ptf_uuid)
            if tx:
                transactions.append(tx)

    # crossEntry-Transaktionen außerhalb von Portfolios
    for tx_elem in root.xpath("//portfolio-transaction"):
        if any(tx_elem is e for e in seen_elems):
            continue
        uuid = _get_text(tx_elem, "uuid")
        if uuid and uuid in seen_uuids:
            continue
        if uuid:
            seen_uuids.add(uuid)
        seen_elems.append(tx_elem)
        # DOM-Ancestry: Portfolio-UUID aus nächstem Vorfahren-Portfolio holen
        ptf_uuid = _find_ancestor_portfolio_uuid(tx_elem)
        tx = _parse_portfolio_transaction(tx_elem, portfolio_uuid=ptf_uuid)
        if tx:
            transactions.append(tx)

    # Konto-Transaktionen (Dividenden)
    for acc_elem in root.xpath("//client/accounts/account"):
        acc_uuid = _get_text(acc_elem, "uuid")
        ptf_uuid = account_to_portfolio.get(acc_uuid) if acc_uuid else None
        for tx_elem in acc_elem.xpath("transactions/account-transaction"):
            uuid = _get_text(tx_elem, "uuid")
            if uuid and uuid in seen_uuids:
                continue
            if uuid:
                seen_uuids.add(uuid)
            tx = _parse_account_transaction(tx_elem, portfolio_uuid=ptf_uuid)
            if tx:
                transactions.append(tx)

    return transactions


def _find_ancestor_portfolio_uuid(elem: etree._Element) -> str | None:
    """Suche in DOM-Ancestry nach einem Portfolio-Element und gib dessen UUID zurück."""
    parent = elem.getparent()
    while parent is not None:
        if parent.tag == "portfolio":
            return _get_text(parent, "uuid")
        parent = parent.getparent()
    return None


def _parse_portfolio_transaction(
    elem: etree._Element, portfolio_uuid: str | None = None
) -> Transaction | None:
    """Parst eine Portfolio-Transaktion (Kauf/Verkauf)."""
    typ_str = _get_text(elem, "type", "")
    typ_map = {
        "BUY": TransaktionsTyp.KAUF,
        "SELL": TransaktionsTyp.VERKAUF,
        "DELIVERY_INBOUND": TransaktionsTyp.EINLIEFERUNG,
        "DELIVERY_OUTBOUND": TransaktionsTyp.AUSLIEFERUNG,
    }
    typ = typ_map.get(typ_str)
    if typ is None:
        return None

    datum_str = _get_text(elem, "date")
    if datum_str is None:
        return None

    # Security UUID - kann direkt oder über Referenz sein
    security_uuid = _get_security_uuid(elem)
    if not security_uuid:
        return None

    shares_str = _get_text(elem, "shares", "0")
    amount_str = _get_text(elem, "amount", "0")
    fees_str = _get_text(elem, "fees", "0")
    taxes_str = _get_text(elem, "taxes", "0")

    stuecke = _to_shares(shares_str)
    gesamtbetrag = _to_money(amount_str)
    gebuehren = _to_money(fees_str)
    steuern = _to_money(taxes_str)

    kurs = gesamtbetrag / stuecke if stuecke > 0 else Decimal("0")

    return Transaction(
        datum=_parse_date(datum_str),
        typ=typ,
        security_uuid=security_uuid,
        stuecke=stuecke,
        kurs=kurs,
        gesamtbetrag=gesamtbetrag,
        gebuehren=gebuehren,
        steuern=steuern,
        portfolio_uuid=portfolio_uuid,
    )


def _parse_account_transaction(
    elem: etree._Element, portfolio_uuid: str | None = None
) -> Transaction | None:
    """Parst eine Konto-Transaktion (Dividende, Zinsen)."""
    typ_str = _get_text(elem, "type", "")
    if typ_str != "DIVIDENDS":
        return None

    datum_str = _get_text(elem, "date")
    if datum_str is None:
        return None

    security_uuid = _get_security_uuid(elem)
    if not security_uuid:
        return None

    shares_str = _get_text(elem, "shares", "0")
    amount_str = _get_text(elem, "amount", "0")
    taxes_str = _get_text(elem, "taxes", "0")

    stuecke = _to_shares(shares_str) if shares_str != "0" else Decimal("1")
    gesamtbetrag = _to_money(amount_str)

    return Transaction(
        datum=_parse_date(datum_str),
        typ=TransaktionsTyp.DIVIDENDE,
        security_uuid=security_uuid,
        stuecke=stuecke,
        kurs=Decimal("0"),
        gesamtbetrag=gesamtbetrag,
        steuern=_to_money(taxes_str),
        portfolio_uuid=portfolio_uuid,
    )


def _extract_kurse(root: etree._Element) -> list[HistorischerKurs]:
    """Extrahiere historische Kurse."""
    kurse = []
    for sec_elem in root.xpath("//client/securities/security"):
        uuid = _get_text(sec_elem, "uuid", "")
        if not uuid:
            continue

        for price_elem in sec_elem.xpath(".//prices/price"):
            t_attr = price_elem.get("t")
            v_attr = price_elem.get("v")
            if t_attr and v_attr:
                try:
                    datum = _parse_date(t_attr)
                    kurs = _to_shares(v_attr)
                    kurse.append(
                        HistorischerKurs(
                            security_uuid=uuid, datum=datum, kurs=kurs
                        )
                    )
                except (ValueError, TypeError):
                    continue
    return kurse


def _get_text(
    elem: etree._Element, tag: str, default: str | None = None
) -> str | None:
    """Hole Text eines Kind-Elements."""
    child = elem.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def _get_security_uuid(elem: etree._Element) -> str | None:
    """Extrahiere die Security-UUID aus einer Transaktion.

    Sucht in verschiedenen PP-XML-Formaten:
    - Direktes <security><uuid> Kind
    - Referenz über security Element mit reference-Attribut
    """
    # Direkt als Kind-Element
    sec_elem = elem.find("security")
    if sec_elem is not None:
        # Prüfe auf reference
        target = _resolve_reference(sec_elem)
        if target is not None:
            uuid_elem = target.find("uuid")
            if uuid_elem is not None and uuid_elem.text:
                return uuid_elem.text.strip()
        # Direkte UUID
        uuid_elem = sec_elem.find("uuid")
        if uuid_elem is not None and uuid_elem.text:
            return uuid_elem.text.strip()

    return None


def parse_portfolio_file(filepath: str | Path) -> PortfolioData:
    """Lese und parse eine Portfolio Performance Datei.

    Unterstützt .xml und .portfolio (ZIP) Dateien.
    """
    filepath = Path(filepath)

    if filepath.suffix == ".portfolio":
        # ZIP-Datei: XML darin finden
        with zipfile.ZipFile(filepath, "r") as zf:
            xml_names = [n for n in zf.namelist() if n.endswith(".xml")]
            if not xml_names:
                raise ValueError("Keine XML-Datei in der .portfolio-Datei gefunden")
            xml_content = zf.read(xml_names[0])
            root = etree.fromstring(xml_content)
    else:
        tree = etree.parse(str(filepath))
        root = tree.getroot()

    portfolios = _extract_portfolios(root)
    return PortfolioData(
        securities=_extract_securities(root),
        transactions=_extract_transactions(root, portfolios),
        kurse=_extract_kurse(root),
        portfolios=portfolios,
    )
