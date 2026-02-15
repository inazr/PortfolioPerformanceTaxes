"""GUI-Modul für SteuerPP."""


class _fmt:
    """Formatierungshelfer für die GUI."""

    @staticmethod
    def euro(value) -> str:
        """Formatiere als Euro-Betrag: 1.234,56 €"""
        from decimal import Decimal
        v = Decimal(str(value))
        s = f"{v:,.2f}"
        # Englisch -> Deutsch: 1,234.56 -> 1.234,56
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s} €"

    @staticmethod
    def percent(value) -> str:
        """Formatiere als Prozentwert: 26,38 %"""
        from decimal import Decimal
        v = Decimal(str(value)) * 100
        s = f"{v:.2f}".replace(".", ",")
        return f"{s} %"

    @staticmethod
    def decimal(value) -> str:
        """Formatiere Decimal mit deutschem Dezimalzeichen."""
        from decimal import Decimal
        v = Decimal(str(value))
        # Zeige bis zu 8 Nachkommastellen, aber entferne trailing zeros
        s = f"{v:.8f}".rstrip("0").rstrip(".")
        s = s.replace(".", ",")
        return s

    @staticmethod
    def datum(value) -> str:
        """Formatiere Datum als DD.MM.YYYY."""
        return value.strftime("%d.%m.%Y")
