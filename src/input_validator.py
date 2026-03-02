"""
Input Validation mit Pydantic für alle User-Inputs.
Stellt sicher, dass alle Parameter korrekt typisiert und validiert sind.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional


class WhatIfRequest(BaseModel):
    """Validierung für /what_if Befehl"""
    coin: str = Field(..., min_length=1, max_length=10, description="Coin Symbol (z.B. BTC)")
    change_percent: float = Field(..., description="Prozentuale Änderung (z.B. -20 für 20% Verkauf)")

    @validator('coin')
    def validate_coin_format(cls, v):
        """Coin-Symbol muss uppercase sein"""
        return v.upper()


class SetIntervalRequest(BaseModel):
    """Validierung für /set_interval Befehl"""
    hours: int = Field(..., ge=1, le=24, description="Intervall in Stunden (1-24)")


class NextInvestRequest(BaseModel):
    """Validierung für /next Befehl – Investment-Empfehlung für einen neuen Betrag."""
    amount: float = Field(
        ...,
        ge=1.0,
        le=100000.0,
        description="Investitionsbetrag in EUR (1–100.000)"
    )

    @validator('amount')
    def round_amount(cls, v):
        """Betrag auf 2 Dezimalstellen runden."""
        return round(v, 2)


def validate_what_if_args(args: list) -> tuple[bool, Optional[WhatIfRequest], str]:
    """Validiert /what_if Argumente"""
    if len(args) < 2:
        return False, None, "Usage: /what_if <COIN> <change_percent>\nBeispiel: /what_if BTC -20 (verkaufe 20% von BTC)"

    try:
        coin = args[0]
        change_percent = float(args[1])

        request = WhatIfRequest(
            coin=coin,
            change_percent=change_percent
        )
        return True, request, ""
    except ValueError as e:
        return False, None, f"Invalid numbers: {str(e)}"
    except Exception as e:
        return False, None, f"Validation error: {str(e)}"


def validate_set_interval_args(args: list) -> tuple[bool, Optional[SetIntervalRequest], str]:
    """Validiert /set_interval Argumente"""
    if len(args) != 1:
        return False, None, "Usage: /set_interval <hours>"

    try:
        hours = int(args[0])
        request = SetIntervalRequest(hours=hours)
        return True, request, ""
    except ValueError:
        return False, None, "Hours must be an integer"


def validate_next_invest_args(args: list) -> tuple[bool, Optional[NextInvestRequest], str]:
    """Validiert /next Argumente.

    Args:
        args: Liste der Kommandozeilen-Argumente (erwartet genau 1: EUR-Betrag)

    Returns:
        Tuple aus (valid, NextInvestRequest | None, Fehlermeldung)
    """
    if len(args) != 1:
        return (
            False,
            None,
            "Usage: /next <EUR-Betrag>\nBeispiel: /next 500 (Empfehlung für 500 EUR Investment)"
        )

    try:
        amount = float(args[0].replace(',', '.'))
        request = NextInvestRequest(amount=amount)
        return True, request, ""
    except ValueError:
        return False, None, "❌ Ungültiger Betrag. Bitte eine Zahl eingeben (z.B. /next 500)"
    except Exception as e:
        return False, None, f"❌ Validierungsfehler: {str(e)}"
