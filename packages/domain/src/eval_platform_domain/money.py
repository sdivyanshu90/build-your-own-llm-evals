"""Decimal-safe monetary value objects."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

_QUANTUM = Decimal("0.000000000001")


@dataclass(frozen=True, slots=True)
class Money:
    """A non-negative fixed-point monetary amount and ISO-style currency code."""

    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        try:
            normalized = self.amount.quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)
        except InvalidOperation as error:
            raise ValueError("money amount must be a finite decimal") from error
        if not normalized.is_finite() or normalized < 0:
            raise ValueError("money amount must be finite and non-negative")
        currency = self.currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter alphabetic code")
        object.__setattr__(self, "amount", normalized)
        object.__setattr__(self, "currency", currency)

    def __add__(self, other: Money) -> Money:
        """Add values with the same currency."""

        self._require_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        """Subtract without allowing a negative result."""

        self._require_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def _require_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError("money currencies must match")
