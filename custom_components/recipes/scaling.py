"""Scale the amount at the start of an ingredient line ("250 g pasta" -> "500 g pasta")."""

from __future__ import annotations

import re

FRACTIONS = {"½": 1 / 2, "¼": 1 / 4, "¾": 3 / 4, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 1 / 8}
_FRAC_CHARS = "".join(FRACTIONS)
_NUM = r"\d+(?:[.,]\d+)?"
# One amount: "1½", "1 ½", "½", "1/2", "1 1/2", "0,5", "250".
_AMOUNT = rf"(?:\d+\s*[{_FRAC_CHARS}]|[{_FRAC_CHARS}]|\d+\s+\d+/\d+|\d+/\d+|{_NUM})"
_LEADING = re.compile(rf"^\s*(?P<a>{_AMOUNT})(?:\s*[-–]\s*(?P<b>{_AMOUNT}))?(?P<rest>.*)$", re.DOTALL)


def _parse(text: str) -> float:
    text = text.strip()
    if m := re.fullmatch(rf"(\d+)\s*([{_FRAC_CHARS}])", text):
        return int(m[1]) + FRACTIONS[m[2]]
    if text in FRACTIONS:
        return FRACTIONS[text]
    if m := re.fullmatch(r"(\d+)\s+(\d+)/(\d+)", text):
        return int(m[1]) + int(m[2]) / int(m[3])
    if m := re.fullmatch(r"(\d+)/(\d+)", text):
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


def scale_line(line: str, factor: float) -> str:
    """Return the ingredient line with its leading amount multiplied by factor."""
    if abs(factor - 1) < 1e-9:
        return line
    m = _LEADING.match(line)
    if not m:
        return line
    rest = m["rest"]
    # "2tenen" or "250g" are fine, but "2025-recipe" style words are not amounts.
    if rest and rest[0].isalnum() and not re.match(r"[a-zA-Zµ]", rest[0]):
        return line
    comma = "," in m["a"] or "," in (m["b"] or "")
    amount = _format(_parse(m["a"]) * factor, comma)
    if m["b"]:
        amount += "-" + _format(_parse(m["b"]) * factor, comma)
    return amount + rest


def scale_ingredients(ingredients: list[str], servings: int | None, target: int | None) -> list[str]:
    """Scale a recipe for `servings` people to `target` people."""
    if not servings or not target or servings == target:
        return list(ingredients)
    factor = target / servings
    return [scale_line(line, factor) for line in ingredients]
