"""Menu style resolver — keeps Rich styles and TCSS variables in sync.

Textual 8.2 cannot read CSS variables from Rich renderables, so every
widget that builds a Rich renderable (a list row, a tree node, a check
marker) resolves the active palette through :class:`MenuStyle`. The
same palette also feeds ``App.get_css_variables()``, so the terminal
and the rendered Rich objects stay visually consistent.

All colors are the gothic-luxury identity values; accent triple is
injected per-theme via :meth:`MenuStyle.with_palette`.
"""

from __future__ import annotations

from rich.style import Style, StyleType

from requiem.themes.palettes import Palette, get_theme


class MenuStyle:
    """Resolved menu style set for one active palette.

    Construct via :meth:`for_theme` or :meth:`from_palette`; the result
    exposes ``Style`` objects for direct use in Rich renderables and
    the raw palette hex strings for TCSS variable injection.
    """

    #: Base surfaces (identical across all themes).
    BG: str = "#0C0A0B"
    BG_RECESSED: str = "#171316"
    BG_ELEVATED: str = "#1B171F"
    TEXT: str = "#E8E1E5"
    TEXT_MUTED: str = "#82777D"
    BORDER: str = "#2A242D"
    SUCCESS: str = "#5A9E6F"

    def __init__(self, palette: Palette) -> None:
        self._palette = palette

    @classmethod
    def for_theme(cls, name: str = "classic") -> MenuStyle:
        """Build a style set for a named theme (falls back to classic)."""
        return cls(get_theme(name))

    @classmethod
    def from_palette(cls, palette: Palette) -> MenuStyle:
        """Build a style set from an explicit palette instance."""
        return cls(palette)

    @property
    def palette(self) -> Palette:
        return self._palette

    # ── Rich style objects (use in Static(...), Text(style=...), Panel) ──

    @property
    def accent(self) -> StyleType:
        """Primary accent color (e.g. Blood Crimson in classic)."""
        return self._palette.primary_accent

    @property
    def accent_deep(self) -> StyleType:
        return self._palette.deep_accent

    @property
    def gold(self) -> StyleType:
        """Rare premium emphasis (Antique Gold in classic)."""
        return self._palette.secondary_accent

    @property
    def success(self) -> StyleType:
        return self.SUCCESS

    @property
    def text(self) -> StyleType:
        return self.TEXT

    @property
    def text_muted(self) -> StyleType:
        return self.TEXT_MUTED

    # Composed styles ─────────────────────────────────────────────────

    @property
    def row_selected(self) -> Style:
        """Selected row: elevated background + accent gutter."""
        return Style(
            bgcolor=self._palette.elevated_iron,
            color=self.TEXT,
            bold=True,
        )

    @property
    def row_hover(self) -> Style:
        return Style(
            bgcolor=self._palette.dark_iron,
            color=self.TEXT,
        )

    @property
    def row_disabled(self) -> Style:
        return Style(
            color=self.TEXT_MUTED,
            dim=True,
        )

    @property
    def section_header(self) -> Style:
        return Style(
            color=self.TEXT_MUTED,
            italic=True,
        )

    @property
    def marker(self) -> Style:
        """Selected-row left-gutter marker '▸' in accent color."""
        return Style(
            color=self._palette.primary_accent,
            bold=True,
        )

    # TCSS variable dict ─────────────────────────────────────────────

    def css_variables(self) -> dict[str, str]:
        """Return the ``$requiem-*`` variable mapping for
        ``App.get_css_variables()``. Keeps TCSS and Rich in sync."""
        p = self._palette
        return {
            "requiem-bg": p.obsidian,
            "requiem-bg-recessed": p.dark_iron,
            "requiem-bg-elevated": p.elevated_iron,
            "requiem-text": p.ash_white,
            "requiem-text-muted": p.muted_ash,
            "requiem-border": p.iron_border,
            "requiem-accent": p.primary_accent,
            "requiem-accent-deep": p.deep_accent,
            "requiem-accent-alt": p.secondary_accent,
            "requiem-success": self.SUCCESS,
            "requiem-error": p.primary_accent,
        }

    def with_palette(self, palette: Palette) -> MenuStyle:
        """Return a new MenuStyle resolved against *palette*."""
        return type(self)(palette)

    # ── Row render helper ─────────────────────────────────────────────

    def row_style(
        self,
        *,
        selected: bool = False,
        hovered: bool = False,
        disabled: bool = False,
    ) -> StyleType:
        """Pick the row background/color style for a given state."""
        if disabled:
            return self.row_disabled
        if selected:
            return self.row_selected
        if hovered:
            return self.row_hover
        return self.text_muted
