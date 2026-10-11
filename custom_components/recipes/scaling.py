"""Ingredients are stored as {amount, unit, name}. Only `amount` is ever scaled.

Amounts are free text that must be a number: "250", "0,5", "0.5", "½", "1½",
"1/2", "1 1/2", or a range of those ("2-3"). An empty amount means "no amount".
"""

from __future__ import annotations

import re
from typing import Any

FRACTIONS = {"½": 1 / 2, "¼": 1 / 4, "¾": 3 / 4, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 1 / 8}
_F = "".join(FRACTIONS)
_ONE = rf"(?:\d+\s*[{_F}]|[{_F}]|\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?)"
_AMOUNT = re.compile(rf"^\s*({_ONE})(?:\s*[-–]\s*({_ONE}))?\s*$")
_LEADING = re.compile(rf"^\s*({_ONE}(?:\s*[-–]\s*{_ONE})?)(?=\s|$)\s*(.*)$", re.DOTALL)


class AmountError(ValueError):
    """The amount is not a number."""


def _parse(text: str) -> float:
    text = text.strip()
    if m := re.fullmatch(rf"(\d+)\s*([{_F}])", text):
        return int(m[1]) + FRACTIONS[m[2]]
    if text in FRACTIONS:
        return FRACTIONS[text]
    if m := re.fullmatch(r"(\d+)\s+(\d+)/(\d+)", text):
        return int(m[1]) + int(m[2]) / int(m[3])
    if m := re.fullmatch(r"(\d+)/(\d+)", text):
        if int(m[2]) == 0:
            raise AmountError(text)
        return int(m[1]) / int(m[2])
    return float(text.replace(",", "."))


def _format(value: float, comma: bool) -> str:
    whole = int(value)
    rest = value - whole
    if abs(rest) < 0.02:
        return str(whole)
    if abs(rest - 1) < 0.02:
        return str(whole + 1)
    for char, frac in FRACTIONS.items():
        if abs(rest - frac) < 0.02:
            return f"{whole}{char}" if whole else char
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if comma else text


def normalize_amount(amount: Any) -> str:
    """Check an amount and write it in a standard form ('0,5' -> '½'). Raises AmountError."""
    if amount is None:
        return ""
    if isinstance(amount, (int, float)) and not isinstance(amount, bool):
        return _format(float(amount), False)
    text = str(amount).strip()
    if not text:
        return ""
    m = _AMOUNT.match(text)
    if not m:
        raise AmountError(text)
    comma = "," in text
    out = _format(_parse(m[1]), comma)
    if m[2]:
        out += "-" + _format(_parse(m[2]), comma)
    return out


def scale_amount(amount: str, factor: float) -> str:
    if not amount or abs(factor - 1) < 1e-9:
        return amount
    m = _AMOUNT.match(amount)
    if not m:
        return amount
    comma = "," in amount
    out = _format(_parse(m[1]) * factor, comma)
    if m[2]:
        out += "-" + _format(_parse(m[2]) * factor, comma)
    return out


def ingredient_from_text(line: str) -> dict[str, str]:
    """Plain text line -> ingredient. Only a leading number is taken out; nothing is guessed."""
    line = line.strip()
    m = _LEADING.match(line)
    if m and m[2]:
        return {"amount": normalize_amount(m[1]), "unit": "", "name": m[2].strip()}
    return {"amount": "", "unit": "", "name": line}


def format_ingredient(ing: dict[str, str]) -> str:
    return " ".join(p for p in (ing.get("amount", ""), ing.get("unit", ""), ing.get("name", "")) if p)


def scale_ingredients(ingredients: list[dict[str, str]], servings: int | None, target: int | None) -> list[dict[str, str]]:
    """Scale a recipe for `servings` people to `target` people."""
    if not servings or not target or servings == target:
        return [dict(i) for i in ingredients]
    factor = target / servings
    return [{**i, "amount": scale_amount(i.get("amount", ""), factor)} for i in ingredients]
