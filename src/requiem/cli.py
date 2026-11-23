"""REQUIEM CLI — top-level entrypoint.

Usage:
    requiem                 # launch TUI
    requiem --version       # print version
    requiem check          # verify installation and dependencies
    requiem init           # create .requiem/ project config
    requiem list-providers # list configured providers
    requiem test <provider>  # test a provider connection
    requiem run <workflow>  # run a workflow headlessly (no TUI)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from requiem import __version__

logger = logging.getLogger("requiem.cli")


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(name)-28s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _cmd_check() -> int:
    """Verify the installation works end-to-end."""
    print(f"REQUIEM v{__version__}")
    ok = True

    # Core imports
    for mod in (
        "requiem.config.loader",
        "requiem.config.manager",
        "requiem.providers.base",
        "requiem.providers.registry",
        "requiem.security.credentials",
        "requiem.themes.manager",
        "requiem.core.application",
    ):
        try:
            __import__(mod)
            print(f"  [OK]  {mod}")
        except ImportError as e:
            print(f"  [ERR] {mod}: {e}")
            ok = False

    # Textual
    try:
        import textual  # noqa: F401
        print(f"  [OK]  textual {textual.__version__}")
    except ImportError as e:
        print(f"  [ERR]  textual: {e}")
        ok = False

    # httpx
    try:
        import httpx  # noqa: F401
        print(f"  [OK]  httpx {httpx.__version__}")
    except ImportError as e:
        print(f"  [ERR]  httpx: {e}")
        ok = False

    # pydantic
    try:
        import pydantic  # noqa: F401
        print(f"  [OK]  pydantic {pydantic.__version__}")
    except ImportError as e:
        print(f"  [ERR]  pydantic: {e}")
        ok = False

    # keyring
    try:
        import importlib.metadata

        import keyring  # noqa: F401
        print(f"  [OK]  keyring {importlib.metadata.version('keyring')}")
    except ImportError as e:
        print(f"  [ERR]  keyring: {e}")
        ok = False

    print("\nAll checks passed." if ok else "\nSome checks failed.")
    return 0 if ok else 1


def _cmd_init(project_root: Path) -> int:
    """Create .requiem/ project config directory structure."""
    from requiem.config.paths import (
        project_agents_dir,
        project_artifacts_dir,
        project_logs_dir,
        project_requiem_dir,
        project_workflows_dir,
    )

    for d in (
        project_requiem_dir(project_root),
        project_workflows_dir(project_root),
        project_agents_dir(project_root),
        project_artifacts_dir(project_root),
        project_logs_dir(project_root),
    ):
        print(f"  created: {d}")
    print("\nProject .requiem/ directory initialized.")
    print("Add workflow definitions to .requiem/workflows/ to get started.")
    return 0


def _cmd_list_providers() -> int:
    """List configured providers from user config."""
    from requiem.config.loader import load_config

    cfg = load_config()
    if not cfg.providers:
        print("No providers configured yet.")
        print("Launch `requiem` to run onboarding, or add providers manually.")
        return 0

    default = cfg.default_provider
    for p in cfg.providers:
        marker = "*" if p.id == default else " "
        status = "enabled" if p.enabled else "disabled"
        print(f" {marker}  {p.id:<20s}  kind={p.kind:<12s}  {status}")
    print("\n* = default provider")
    return 0


def _cmd_test(provider_id: str) -> int:
    """Test a provider connection headlessly."""
    from requiem.config.loader import load_config
    from requiem.providers.registry import create_provider
    from requiem.security.credentials import CredentialVault

    cfg = load_config()
    prov = next((p for p in cfg.providers if p.id == provider_id), None)
    if prov is None:
        print(f"Provider '{provider_id}' not found. Use `requiem list-providers` to see available providers.")
        return 1

    vault = CredentialVault()
    key = vault.retrieve(prov.id) or prov.credentials.api_key_ref

    provider = create_provider(
        prov.kind,
        base_url=prov.credentials.base_url,
        api_key=key,
        timeout_s=prov.credentials.timeout_s,
        custom_headers=prov.credentials.custom_headers,
        compat=prov.credentials.compat,
    )

    async def _run() -> None:
        ok, msg = await provider.validate_connection(api_key=key)
        await provider.close()
        print(f"  {provider.display_name}: {'OK' if ok else 'FAILED'}")
        if not ok:
            print(f"  {msg}")

    try:
        asyncio.run(_run())
        return 0
    except Exception as e:
        print(f"  Error: {e}")
        return 1


def _cmd_run(workflow_path: Path) -> int:
    """Run a workflow definition headlessly (no TUI)."""
    from requiem.workflows.executor import WorkflowExecutor
    from requiem.workflows.loader import load_workflow

    wf = load_workflow(workflow_path)
    print(f"Loading workflow: {wf.name} ({len(wf.tasks)} tasks)")

    async def _run() -> None:
        executor = WorkflowExecutor()
        await executor.execute(wf)

    try:
        asyncio.run(_run())
        return 0
    except Exception as e:
        print(f"  Error: {e}")
        return 1


def _cmd_tui() -> int:
    """Launch the Textual TUI."""
    from requiem.tui.app import RequiemApp

    app = RequiemApp()
    app.run()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="requiem",
        description="REQUIEM — Multi-agent AI orchestration and development environment.",
    )
    parser.add_argument("--version", action="version", version=f"requiem {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress INFO logs")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("check", help="Verify installation and dependencies")
    sub.add_parser("init", help="Create .requiem/ project config")
    sub.add_parser("list-providers", help="List configured providers")

    p_test = sub.add_parser("test", help="Test a provider connection")
    p_test.add_argument("provider", help="Provider ID to test")

    p_run = sub.add_parser("run", help="Run a workflow headlessly")
    p_run.add_argument("workflow", type=Path, help="Path to workflow definition file")

    args = parser.parse_args()

    if args.quiet:
        _setup_logging("WARNING")
    elif args.verbose:
        _setup_logging("DEBUG")
    else:
        _setup_logging("INFO")

    match args.command:
        case "check":
            sys.exit(_cmd_check())
        case "init":
            sys.exit(_cmd_init(Path.cwd()))
        case "list-providers":
            sys.exit(_cmd_list_providers())
        case "test":
            sys.exit(_cmd_test(args.provider))
        case "run":
            sys.exit(_cmd_run(args.workflow))
        case None:
            # No subcommand — launch TUI
            sys.exit(_cmd_tui())
        case _:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
