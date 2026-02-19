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
    def decimal(value, max_decimals: int = 4) -> str:
        """Formatiere Decimal mit deutschem Dezimalzeichen.

        Maximal max_decimals Nachkommastellen. Rundet auf, wenn der
        abgeschnittene Rest weniger als 2 % des Gesamtwerts ausmacht.
        """
        from decimal import Decimal, ROUND_UP, ROUND_DOWN
        v = Decimal(str(value))
        quantize_exp = Decimal(10) ** -max_decimals

        truncated = v.quantize(quantize_exp, rounding=ROUND_DOWN)
        rest = v - truncated

        if rest > 0 and v != 0:
            anteil = rest / v
            if anteil < Decimal("0.02"):
                v = v.quantize(quantize_exp, rounding=ROUND_UP)
            else:
                v = truncated

        s = f"{v:.{max_decimals}f}".rstrip("0").rstrip(".")
        s = s.replace(".", ",")
        return s

    @staticmethod
    def datum(value) -> str:
        """Formatiere Datum als DD.MM.YYYY."""
        return value.strftime("%d.%m.%Y")
