# REQUIEM

**Multi-agent AI orchestration and development environment.**

REQUIEM is a Python-based terminal application that lets you communicate with an AI orchestrator,
delegate work to specialized agents, and execute multi-step workflows through a polished TUI
with a distinctive gothic-luxury visual identity.

---

## Features

- **Multi-provider support** — OpenAI, Anthropic/Claude, OpenRouter, 9Router, and custom OpenAI-compatible endpoints
- **Real streaming** — All providers normalize to the same `StreamEvent` format; the TUI never sees provider-specific protocols
- **Tool calling** — Filesystem, shell, and HTTP tools with permission enforcement and audit logging
- **Multi-agent workflow engine** — Task DAGs, sequential/parallel execution, reviewer loops, checkpointing and resume
- **5 themes** — Classic (Blood Crimson), Blue, Purple, Magenta, Grey — all sharing the same Obsidian/Dark Iron base
- **Secure credentials** — API keys stored in the OS keyring (or env vars); never written to config files or logs
- **First-run onboarding** — Wizard walks through theme, provider, credentials, and model selection
- **Command palette** — `Ctrl+P` for searchable access to all actions
- **Resumable workflows** — SQLite persistence; interrupted workflows can be resumed without repeating completed tasks

---

## Requirements

- **Python 3.11+** (3.14 tested)
- A compatible terminal (Windows Terminal, macOS Terminal/iTerm2, Linux GNOME/Terminal)
- Optional: Nerd Fonts for enhanced icons (falls back to plain Unicode without them)

---

## Installation

```bash
# Clone the repository
git clone <url> && cd requiem-harness

# Install in editable mode (dev)
pip install -e .

# Or install the dev tooling too
pip install -e ".[dev]"
```

### Verify the install

```bash
requiem check
```

---

## First Launch

```bash
requiem
```

On first run, the **onboarding wizard** appears automatically:

1. **Welcome** — REQUIEM emblem and product description
2. **Theme** — Choose from 5 themes (Classic, Blue, Purple, Magenta, Grey) with live color previews
3. **Provider** — Select OpenAI, Anthropic, OpenRouter, 9Router, or Custom
4. **Credentials** — Enter your API key (masked) or use the environment variable
5. **Model** — Choose or enter a model name
6. **Save** — Configuration is written to the platform config directory

You can re-run onboarding at any time from **Settings → Providers** (F5).

---

## Provider Configuration

### OpenAI / ChatGPT

```bash
export OPENAI_API_KEY="sk-..."
requiem
```

Or configure a custom base URL for Azure OpenAI or a proxy.

### Anthropic / Claude

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
requiem
```

### OpenRouter

```bash
export OPENROUTER_API_KEY="sk-or-..."
requiem
```

OpenRouter supports provider routing via the `routing` metadata field.

### 9Router (First-Class Support)

9Router is a configurable OpenAI-compatible API aggregator. Configure your own instance:

```toml
# In your requiem config file (platformdirs/requiem/config.toml):
[[providers]]
id = "my-router9"
name = "My 9Router Instance"
kind = "router9"
enabled = true
default_model = "gpt-4o-mini"

[providers.credentials]
api_key_ref = "my-router9"          # vault reference; the key itself is in keyring
base_url = "http://localhost:8080/v1"   # your 9Router instance URL
custom_headers = {}                # add auth headers if needed
timeout_s = 120.0
compat = {}                        # provider-specific compatibility options
```

Store the API key in the credential vault:

```bash
# The key is looked up via keyring under service "requiem", user "my-router9"
# Or set the environment variable:
export ROUTER9_API_KEY="your-key-here"
```

**9Router-specific notes:**
- Set `base_url` to your own 9Router instance (do **not** hardcode `api.router9.com`)
- Some 9Router builds don't expose `/models`; REQUIEM falls back to a completion probe
- Custom headers are supported for installations that require `X-API-Key` instead of `Authorization`
- Use `compat` to tune behavior for specific 9Router build variants

### Custom OpenAI-Compatible

Any endpoint that speaks the OpenAI Chat Completions wire format works:

```toml
[[providers]]
id = "local-llm"
name = "Local LLM"
kind = "custom"
enabled = true

[providers.credentials]
api_key_ref = "local-llm"
base_url = "http://localhost:11434/v1"
model = "llama3"
```

---

## CLI Commands

```bash
requiem                    # Launch TUI
requiem check              # Verify installation
requiem init               # Create .requiem/ project config
requiem list-providers     # Show configured providers
requiem test <provider-id> # Test a provider connection
requiem run <workflow>     # Run a workflow headlessly
requiem --version          # Print version
requiem -v                 # Enable debug logging
```

---

## Themes

All five themes share the same Obsidian/Dark Iron base. Only the accent colors change:

| Theme | Primary Accent | Deep Accent | Secondary Accent |
|-------|---------------|-------------|-----------------|
| Classic | `#C02645` | `#81172F` | `#D4AF72` |
| Blue | `#6C8FA8` | `#405D73` | `#A8BBC7` |
| Purple | `#8D78A8` | `#57476E` | `#C0B0CE` |
| Magenta | `#B16B89` | `#704459` | `#D0A0B1` |
| Grey | `#A7A0A5` | `#655F65` | `#C2BABE` |

Switch themes live from the TUI (**F7** Theme Manager) or via the config file:

```toml
[theme]
active = "blue"   # classic | blue | purple | magenta | grey
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+P` | Command palette |
| `Ctrl+Q` | Quit |
| `Ctrl+C` | Cancel active operation |
| `Ctrl+Enter` | Submit message |
| `F1` | Help |
| `F2` | Agent dashboard |
| `F3` | Workflow runner |
| `F4` | Logs |
| `F5` | Provider manager |
| `F6` | Settings |
| `F7` | Theme manager |
| `Esc` | Close modal / go back |

---

## Running Tests

```bash
# All tests
pytest

# Specific test suite
pytest tests/unit/
pytest tests/providers/

# With coverage
pytest --cov=requiem --cov-report=term-missing

# Lint
ruff check src/ tests/

# Type check
mypy src/requiem/
```

---

## Configuration Locations

| File | Location |
|------|----------|
| User config | `platformdirs/requiem/config.toml` (OS-specific) |
| Workflow DB | `platformdirs/requiem/requiem.db` |
| Project config | `.requiem/config.toml` (in your project root) |
| Workflows | `.requiem/workflows/` |
| Agents | `.requiem/agents/` |
| Artifacts | `.requiem/artifacts/` |
| Logs | `.requiem/logs/` |

API keys are stored in the OS keyring (Windows Credential Manager, macOS Keychain,
Linux Secret Service). The environment variable fallback uses:
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `ROUTER9_API_KEY`.

---

## Tool Permissions

REQUIEM enforces permissions in code, not in prompts:

| Tool | Permission Level | Approval Required |
|------|-----------------|-------------------|
| `list_directory` | READ | No |
| `read_file` | READ | No |
| `search_files` | READ | No |
| `search_in_file` | READ | No |
| `create_file` | WRITE | No |
| `modify_file` | WRITE | No |
| `delete_file` | DESTRUCTIVE | **Yes** |
| `execute_command` | EXECUTE | **Yes** |
| `http_request` | NETWORK | **Yes** |

Filesystem operations are restricted to the configured workspace root.
HTTP requests to private/internal IPs are blocked by default (SSRF protection).

---

## Known Limitations

- The multi-agent workflow engine (Phases 3–4) is in progress; the tool registry and provider layer are fully functional
- MCP integration is not yet implemented
- Cost tracking shows token counts; monetary cost requires user-configured pricing data
