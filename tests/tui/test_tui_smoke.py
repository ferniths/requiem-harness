"""TUI smoke tests — verify the application shell and navigation work.

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
    """RequiemApp composes the shell and mounts the chat view."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        assert pilot.app.screen is not None
        # The nav rail should be present
        nav = pilot.app.query_one("#req-nav-rail")
        assert nav is not None
        # The workspace should have the chat view mounted
        workspace = pilot.app.query_one("#req-workspace")
        assert workspace is not None
        # The composer input exists
        chat_input = pilot.app.query_one("#req-composer-input", Input)
        assert chat_input is not None
        # Status bar exists
        status = pilot.app.query_one("#req-status-bar")
        assert status is not None


@pytest.mark.asyncio
async def test_navigation_to_agents():
    """F2 switches to the Agents view."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("f2")
        await pilot.pause()
        # The agents view should be mounted in the workspace
        workspace = pilot.app.query_one("#req-workspace")
        children = list(workspace.children)
        assert len(children) > 0
        # Check that the active view is now agents
        assert app.active_view == "agents"


@pytest.mark.asyncio
async def test_navigation_to_providers():
    """F5 switches to the Providers view."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("f5")
        await pilot.pause()
        assert app.active_view == "providers"


@pytest.mark.asyncio
async def test_command_palette_opens():
    """Ctrl+P opens the command palette modal."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        # The palette should be on the screen stack
        assert len(app.screen_stack) > 1


@pytest.mark.asyncio
async def test_command_palette_navigation():
    """Arrow keys navigate the command palette list."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        # Should have returned to the main screen
        assert app.active_view in ("chat", "agents", "workflows", "providers", "logs", "settings", "themes", "help")


@pytest.mark.asyncio
async def test_theme_navigation():
    """F7 switches to the Appearance (themes) view."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("f7")
        await pilot.pause()
        assert app.active_view == "themes"


@pytest.mark.asyncio
async def test_logs_view():
    """F4 switches to the Logs view."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("f4")
        await pilot.pause()
        assert app.active_view == "logs"


@pytest.mark.asyncio
async def test_settings_view():
    """F6 switches to the Settings view."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.press("f6")
        await pilot.pause()
        assert app.active_view == "settings"


@pytest.mark.asyncio
async def test_chat_empty_state():
    """The chat view shows an empty state on fresh launch."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        # The empty state widget should be present
        empty = pilot.app.query_one("#req-chat-empty")
        assert empty is not None


@pytest.mark.asyncio
async def test_onboarding_screen_mounts_cleanly():
    """Onboarding screen mounts without a CSS UnresolvedVariableError.

    Regression: the onboarding CSS referenced undefined variables
    ($requiem-accent-secondary, $requiem-text-secondary) that crashed the
    app on first run. Pushing the screen forces its stylesheet to parse.
    """
    from requiem.tui.app import RequiemApp
    from requiem.tui.screens.onboarding import OnboardingScreen

    app = RequiemApp()
    async with app.run_test() as pilot:
        app.push_screen(OnboardingScreen())
        await pilot.pause()
        assert isinstance(app.screen_stack[-1], OnboardingScreen)


@pytest.mark.asyncio
async def test_first_run_launches_onboarding(monkeypatch):
    """On a first run (is_first_run True), the app mounts onboarding automatically."""
    monkeypatch.setattr("requiem.config.loader.is_first_run", lambda: True)
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.screen_stack) > 1
        from requiem.tui.screens.onboarding import OnboardingScreen
        assert isinstance(app.screen_stack[-1], OnboardingScreen)
