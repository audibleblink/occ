"""CLI entry point for occ."""

from __future__ import annotations

import os
import subprocess
import sys

import typer

from occ import __version__
from occ.config import (
    CONFIG_DIR,
    ensure_config_initialized,
    get_config_path,
    reset_config,
)

app = typer.Typer(
    name="occ",
    help="OpenCode Container CLI - Ephemeral development containers pre-loaded with OpenCode.",
    no_args_is_help=True,
)

# Config subcommand group
config_app = typer.Typer(
    name="config",
    help="Manage occ configuration.",
    invoke_without_command=True,
)
app.add_typer(config_app, name="config")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """OpenCode Container CLI."""
    pass


@config_app.callback(invoke_without_command=True)
def config_main(ctx: typer.Context) -> None:
    """Show config directory path if no subcommand given."""
    # Ensure config is initialized
    ensure_config_initialized()

    # If no subcommand was invoked, show config info
    if ctx.invoked_subcommand is None:
        print(f"Configuration directory: {CONFIG_DIR}")
        print(f"Config file: {get_config_path()}")
        print()
        print("Commands:")
        print("  occ config edit   - Edit config.toml in your editor")
        print("  occ config reset  - Reset configuration to defaults")


@config_app.command("reset")
def config_reset(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Reset Dockerfile and config.toml to defaults."""
    if not force:
        confirm = typer.confirm(
            "This will reset your Dockerfile and config.toml to defaults. Continue?"
        )
        if not confirm:
            print("Aborted.")
            raise typer.Exit(0)

    reset_config()
    print(f"Configuration reset to defaults at {CONFIG_DIR}/")


@config_app.command("edit")
def config_edit() -> None:
    """Open config.toml in your editor."""
    ensure_config_initialized()
    config_path = get_config_path()

    # Get editor from environment
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")

    if not editor:
        # Try to find a common editor
        common_editors = ["nano", "vim", "vi"]
        for ed in common_editors:
            try:
                # Check if editor exists
                result = subprocess.run(
                    ["which", ed],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    editor = ed
                    break
            except Exception:
                continue

    if not editor:
        print("Error: No editor found.", file=sys.stderr)
        print()
        print("Set the EDITOR environment variable to your preferred editor:")
        print("  export EDITOR=nano")
        print("  export EDITOR=vim")
        print("  export EDITOR=code")
        print()
        print(f"Or edit the file directly at: {config_path}")
        raise typer.Exit(1)

    # Open editor
    try:
        subprocess.run([editor, str(config_path)])
    except Exception as e:
        print(f"Error opening editor: {e}", file=sys.stderr)
        print(f"Edit the file directly at: {config_path}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
