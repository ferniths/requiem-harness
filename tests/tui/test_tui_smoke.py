"""TUI smoke tests — verify the application launches without crashing.

These tests use Textual's pilot facility to interact with the app.
"""

from __future__ import annotations

import pytest
from textual.widgets import Input


@pytest.fixture(autouse=True)
def _skip_onboarding(monkeypatch):
    """Prevent onboarding from triggering during TUI tests."""
    monkeypatch.setattr("requiem.config.loader.is_first_run", lambda: False)

@pytest.mark.asyncio
async def test_app_launches():
    """RequiemApp can be instantiated and run without crashing."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        # App should have the main screen with chat input
        assert pilot.app.screen is not None
        # Check the chat input exists
        chat_input = pilot.app.query_one("#chat-input", Input)
        assert chat_input is not None


@pytest.mark.asyncio
async def test_help_screen_opens():
    """F1 opens the help modal screen."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("f1")
        await pilot.pause()
        # The help screen should be on the stack
        assert len(app.screen_stack) > 0


@pytest.mark.asyncio
async def test_command_palette_opens():
    """Ctrl+P opens the command palette."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert len(app.screen_stack) > 0


@pytest.mark.asyncio
async def test_themes_screen_opens():
    """F7 opens the theme manager."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("f7")
        await pilot.pause()
        assert len(app.screen_stack) > 0
