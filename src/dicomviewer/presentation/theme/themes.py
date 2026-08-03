"""Theme definitions: color tokens and public theme catalog.

Tokens are the single source of truth for both the QPalette and the QSS
stylesheet, so palette colors and widget styling can never drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ThemeTokens:
    """Color tokens shared between the palette and the stylesheet."""

    window: str
    surface: str
    base: str
    alternate: str
    elevated: str
    border: str
    text: str
    muted: str
    disabled: str
    accent: str
    on_accent: str
    hover: str
    selection: str
    tooltip_bg: str
    tooltip_text: str
    viewer: str
    icon: str
    placeholder: str
    link: str


@dataclass(frozen=True)
class ThemeSpec:
    """A named theme: display metadata plus its color tokens."""

    name: str
    display_name: str
    tokens: ThemeTokens

    def token_values(self) -> Mapping[str, str]:
        """Return the tokens as a plain string mapping for QSS substitution."""
        return asdict(self.tokens)


DARK_TOKENS = ThemeTokens(
    window="#1B1B1F",
    surface="#222228",
    base="#26262C",
    alternate="#2B2B32",
    elevated="#2A2A31",
    border="#3A3A42",
    text="#E8E8EC",
    muted="#9A9AA3",
    disabled="#5C5C66",
    accent="#3B82F6",
    on_accent="#FFFFFF",
    hover="#33333B",
    selection="#3B82F6",
    tooltip_bg="#2E2E36",
    tooltip_text="#E8E8EC",
    viewer="#121216",
    icon="#D0D0D6",
    placeholder="#7A7A84",
    link="#7CB0FF",
)

LIGHT_TOKENS = ThemeTokens(
    window="#F4F4F6",
    surface="#ECECEF",
    base="#FFFFFF",
    alternate="#F7F7F9",
    elevated="#FFFFFF",
    border="#D5D5DB",
    text="#1F1F26",
    muted="#66666E",
    disabled="#A0A0A8",
    accent="#2563EB",
    on_accent="#FFFFFF",
    hover="#E4E4EA",
    selection="#2563EB",
    tooltip_bg="#FFFFFF",
    tooltip_text="#1F1F26",
    viewer="#1A1A20",
    icon="#33333C",
    placeholder="#8A8A92",
    link="#2563EB",
)

THEMES: Mapping[str, ThemeSpec] = {
    "dark": ThemeSpec(name="dark", display_name="Dark", tokens=DARK_TOKENS),
    "light": ThemeSpec(name="light", display_name="Light", tokens=LIGHT_TOKENS),
}
