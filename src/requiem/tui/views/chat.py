"""Chat view — the primary REQUIEM user experience.

Implements:
- Conversation history with user/assistant/system message rendering
- Real provider integration via the provider registry
- Streaming response display
- Multiline input composer
- Empty state with actionable examples
- Cancellation of in-flight generation
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, Label, Static

logger = logging.getLogger("requiem.tui.views.chat")

_EXAMPLE_TASKS = [
    ("Analyze this project", "Give me a structural overview of this repository."),
    ("Review codebase for issues", "Scan the current codebase for common bugs and anti-patterns."),
    ("Explain repository structure", "Describe the directory layout and key modules."),
    ("Debug an error", "Help me understand and fix the error I'm seeing."),
]


class ChatView(Vertical):
    """The main chat workspace.

    This view communicates with the provider layer directly.
    The application shell provides it with:
    - the active provider instance
    - the active model name
    - a callback for updating the status bar
    """

    view_id = "chat"
    view_label = "Chat"
    view_group = "Workspace"

    # Reactive state — triggers UI refresh
    is_busy: reactive[bool] = reactive(False)
    active_provider_name: reactive[str] = reactive("")
    active_model_name: reactive[str] = reactive("")

    def __init__(
        self,
        *,
        on_status: Any = None,  # callable(status: str) → None, updates the status bar
    ) -> None:
        super().__init__(id="req-chat-view")
        self._on_status = on_status
        self._messages: list[dict[str, str]] = []
        self._streaming_widget: Static | None = None
        self._streaming_text = ""
        self._task: Any | None = None
        self._input_history: list[str] = []

    def compose(self) -> ComposeResult:
        with Container(id="req-chat-log"), VerticalScroll(id="req-chat-history"):
            yield Static(id="req-chat-empty")
        # The input composer
        with Container(id="req-composer"):
            yield Input(placeholder="Describe what you want REQUIEM to work on…", id="req-composer-input")
            yield Label("Enter · newline   Ctrl+Enter · send   Esc · cancel", id="req-composer-hints")

    def on_mount(self) -> None:
        self._render_empty_state()
        # Focus the input
        self.query_one("#req-composer-input").focus()

    # ── Provider integration ─────────────────────────────────────────────

    async def send_message(self, text: str | None = None) -> None:
        """Send a message to the active provider.

        If *text* is None, read from the input widget.
        """
        if text is None:
            inp = self.query_one("#req-composer-input", Input)
            text = inp.value.strip()
        if not text or self.is_busy:
            return

        self._input_history.append(text)
        self._add_user_message(text)
        self.is_busy = True
        self._update_status("thinking…")

        # Build conversation
        conversation = self._build_conversation(text)

        # Get the provider from the app
        app = self.app
        provider = getattr(app, "_active_provider", None)
        model = getattr(app, "_active_model", None) or "gpt-4"

        if provider is None:
            self._add_system_message(
                "No provider configured. Open Providers (F5) to connect one, "
                "or run onboarding from the command palette."
            )
            self.is_busy = False
            self._update_status("no provider")
            return

        try:
            api_key = getattr(app, "_resolve_api_key", lambda: None)()
            # Start streaming
            self._streaming_widget = self._start_streaming()
            self._streaming_text = ""
            async for event in provider.stream(
                self._build_request(conversation, model),
                api_key=api_key,
            ):
                if event.type == "content_delta":
                    self._streaming_text += event.content
                    self._update_streaming()
                elif event.type == "finish":
                    break
                elif event.type == "error":
                    self._add_system_message(f"Provider error: {event.error}")
                    self._finish_streaming()
                    self.is_busy = False
                    self._update_status("error")
                    return

            # Complete
            if self._streaming_text:
                self._finalize_assistant_message(self._streaming_text)
            self._finish_streaming()
            self.is_busy = False
            self._update_status("ready")
        except Exception as e:
            self._add_system_message(f"Request failed: {e}")
            self._finish_streaming()
            self.is_busy = False
            self._update_status("error")

    def cancel_generation(self) -> None:
        """Cancel an in-flight generation."""
        if self._task is not None:
            self._task.cancel()
        self._finish_streaming()
        self._add_system_message("Generation cancelled.")
        self.is_busy = False
        self._update_status("ready")

    def _build_request(self, conversation: list[dict[str, str]], model: str) -> Any:
        from requiem.providers.models import ChatMessage, ProviderRequest

        from typing import cast

        messages: list[ChatMessage] = []
        for m in conversation:
            role = cast("Literal['system', 'user', 'assistant', 'tool']", m["role"])
            messages.append(ChatMessage(role=role, content=m["content"]))
        return ProviderRequest(model=model, messages=messages, stream=True)

    def _build_conversation(self, new_message: str) -> list[dict[str, str]]:
        """Build the conversation history for the provider."""
        msgs = self._messages[-20:]  # last 20 for context
        msgs.append({"role": "user", "content": new_message})
        return msgs

    # ── Message rendering ────────────────────────────────────────────────

    def _history(self) -> Any:
        return self.query_one("#req-chat-history")

    def _add_user_message(self, text: str) -> None:
        # Remove empty state if present
        self._dismiss_empty_state()
        # Separator
        self._history().mount(Static("  ", classes="req-msg-separator"))
        label = Static("You", classes="req-msg-user-label")
        body = Text.from_markup(f"  {text}")
        self._history().mount(label)
        self._history().mount(Static(body, id="req-msg-user-body"))
        self._messages.append({"role": "user", "content": text})
        self._scroll_to_bottom()

    def _add_system_message(self, text: str) -> None:
        self._dismiss_empty_state()
        msg = Text(f"⚠ {text}", style="italic")
        self._history().mount(Static(msg, classes="req-msg-system"))
        self._scroll_to_bottom()

    def _start_streaming(self) -> Static:
        """Mount a streaming placeholder and return it for incremental updates."""
        self._dismiss_empty_state()
        label = Static("Assistant", classes="req-msg-assistant-label")
        placeholder = Static("…", id="req-streaming")
        self._history().mount(label)
        self._history().mount(placeholder)
        self._scroll_to_bottom()
        return placeholder

    def _update_streaming(self) -> None:
        if self._streaming_widget is not None:
            self._streaming_widget.update(Markdown(self._streaming_text))
            self._scroll_to_bottom_if_following()

    def _finalize_assistant_message(self, text: str) -> None:
        """Replace the streaming widget with the final markdown-rendered message."""
        if self._streaming_widget is not None:
            self._streaming_widget.update(Markdown(text))
            self._streaming_widget = None
        self._messages.append({"role": "assistant", "content": text})

    def _finish_streaming(self) -> None:
        if self._streaming_widget is not None:
            # Already updated with final content in _finalize
            self._streaming_widget = None
        self._update_status("ready")

    # ── Empty state ──────────────────────────────────────────────────────

    def _render_empty_state(self) -> None:
        """Show the welcome / no-provider empty state."""
        empty: Any = self.query_one("#req-chat-empty")
        p: Any = getattr(self.app, "_theme_mgr", None)
        accent = p.primary_accent if p else "#C02645"
        gold = p.secondary_accent if p else "#D4AF72"
        muted = p.muted_ash if p else "#82777D"

        lines: list[Text] = [
            Text("R E Q U I E M", style=f"bold {gold}"),
            Text("", ),
            Text("Your AI development workbench.", style=muted),
            Text("", ),
        ]
        provider_name = self.active_provider_name or "No provider configured"
        model_name = self.active_model_name or ""
        lines.append(Text(f"Provider: {provider_name}  ·  Model: {model_name}" if model_name else f"Provider: {provider_name}", style=muted))
        lines.append(Text(""))
        lines.append(Text("Try one of these:", style=f"bold {muted}"))
        for label, desc in _EXAMPLE_TASKS:
            lines.append(Text(f"  • {label}  —  {desc}", style=muted))

        empty.update(Panel("\n".join(str(t) for t in lines), title="  ", border_style=accent, padding=(1, 2)))

    def _dismiss_empty_state(self) -> None:
        try:
            empty: Any = self.query_one("#req-chat-empty")
            empty.update(Text(""))
        except Exception:
            pass

    # ── Input actions ────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in the composer (Enter = newline via Shift, Ctrl+Enter = submit)."""
        # Ctrl+Enter is bound at app level; this handles plain Enter
        if event.value:
            app: Any = self.app
            app.action_submit_message()

    def _scroll_to_bottom(self) -> None:
        self._history().scroll_to_bottom()

    def _scroll_to_bottom_if_following(self) -> None:
        """Auto-scroll only if the user is already near the bottom."""
        h = self._history()
        at_bottom = h.scroll_offset_y >= h.max_scroll_y - 5
        if at_bottom:
            self._scroll_to_bottom()

    # ── Status callback ──────────────────────────────────────────────────

    def _update_status(self, status: str) -> None:
        if self._on_status:
            self._on_status(status)

    def clear_conversation(self) -> None:
        """Clear all messages and show the empty state again."""
        self._messages.clear()
        h = self._history()
        h.remove_children("*")
        self._render_empty_state()
        self._update_status("ready")

    # ── History navigation ───────────────────────────────────────────────

    def navigate_history(self, direction: int) -> None:
        """Up/Down in the input recalls previous messages."""
        if not self._input_history:
            return
        idx = direction if direction < 0 else 0
        self._input_history.insert(0, self.query_one("#req-composer-input", Input).value)
        target = self._input_history[min(idx, len(self._input_history) - 1)]
        self.query_one("#req-composer-input", Input).value = target
