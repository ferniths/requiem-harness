"""Theme Manager modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from requiem.themes.palettes import ALL_THEMES, list_theme_names


class ThemesScreen(ModalScreen[None]):
    """Live theme preview and switching."""

    CSS = """
    ThemesScreen {
        content-align: center middle;
        background: rgba(12, 10, 11, 0.92);
    }
    #themes-box {
        width: 50%;
        height: 60%;
        border: solid #2A242D;
        background: $surface;
        padding: 2;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("right", "cycle_forward", "Next"),
        Binding("left", "cycle_backward", "Prev"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._active_name: str = "classic"

    def on_mount(self) -> None:
        # Read the active theme from the app
        app = self.app
        theme_mgr = getattr(app, "_theme_mgr", None)
        if theme_mgr:
            self._active_name = theme_mgr.name

    def _update_display(self) -> None:
        """Update the theme list display without re-mounting widgets."""
        for name in list_theme_names():
            palette = ALL_THEMES[name]
            marker = "★" if name == self._active_name else " "
            swatch = palette.primary_accent
            widget = self.query_one(f"#theme-{name}", Static)
            widget.update(f"{marker}  {name:<10s}  accent={swatch}")

    def action_cycle_forward(self) -> None:
        names = list_theme_names()
        idx = names.index(self._active_name) if self._active_name in names else 0
        self._active_name = names[(idx + 1) % len(names)]
        self._update_display()

    def action_cycle_backward(self) -> None:
        names = list_theme_names()
        idx = names.index(self._active_name) if self._active_name in names else 0
        self._active_name = names[(idx - 1) % len(names)]
        self._update_display()

    def compose(self) -> ComposeResult:
        with Vertical(id="themes-box"):
            yield Label("Theme Manager", id="themes-title")
            for name in list_theme_names():
                palette = ALL_THEMES[name]
                swatch = palette.primary_accent
                yield Static(f"   {name:<10s}  accent={swatch}", id=f"theme-{name}")
            yield Static("Right/Left  cycle  ·  Esc  close")

    def action_close(self) -> None:
        # Apply the selected theme via Textual's theme system
        app = self.app
        if self._active_name != getattr(app, "theme", "textual-dark"):
            app.theme = self._active_name
            theme_mgr = getattr(app, "_theme_mgr", None)
            if theme_mgr:
                theme_mgr.set_theme(self._active_name)
        self._update_display()
        self.dismiss()
