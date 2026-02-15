"""CLI entry point for occ."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from occ import __version__
from occ.config import (
    CONFIG_DIR,
    ensure_config_initialized,
    get_config_path,
    get_dockerfile_path,
    get_extra_mounts,
    load_config,
    needs_rebuild,
    reset_config,
    save_dockerfile_hash,
)
from occ.docker import (
    assemble_mounts,
    attach_to_container,
    build_image,
    check_docker_available,
    cleanup_dangling_images,
    create_container,
    get_container_status,
    image_exists,
    list_occ_containers,
    remove_container,
    sanitize_container_name,
    start_container,
    stop_container,
)
from occ.env import collect_env_vars


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(__version__)
        raise typer.Exit()


def require_docker() -> None:
    """Ensure Docker is available, exit with error if not.

    Raises:
        typer.Exit: If Docker is not running.
    """
    if not check_docker_available():
        print(
            "Error: Docker is not running. Please start Docker and try again.",
            file=sys.stderr,
        )
        raise typer.Exit(1)


def resolve_container_name(project: str | None) -> str:
    """Resolve a project identifier to a container name.

    Args:
        project: Project name, container name (with/without occ- prefix), or None.

    Returns:
        Full container name with occ- prefix.
    """
    if project is None:
        project_path = Path.cwd()
        return sanitize_container_name(str(project_path))

    if project.startswith("occ-"):
        return project
    return f"occ-{project}"


def prompt_running_container() -> str:
    """Prompt user for action when container is running.

    Returns:
        One of: 'attach', 'restart', 'cancel'
    """
    while True:
        try:
            response = (
                input("Container is running. [A]ttach / [R]estart / [C]ancel? ")
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print()  # Newline after ^C
            return "cancel"

        if response in ("a", "attach"):
            return "attach"
        elif response in ("r", "restart"):
            return "restart"
        elif response in ("c", "cancel"):
            return "cancel"
        print("Please enter A, R, or C")


def ensure_container_running(
    path: Path | None = None,
    rebuild: bool = False,
    env: list[str] | None = None,
    verbose: bool = False,
    quiet: bool = False,
) -> str:
    """Ensure a container is running for the given project path.

    Handles the full container lifecycle:
    - Config loading and validation
    - Docker availability check
    - Image build (if needed or --rebuild)
    - Container status prompts (running/stopped)
    - Container creation and startup

    Args:
        path: Project directory path (defaults to cwd).
        rebuild: Force rebuild of container image.
        env: Additional environment variables (VAR=value format).
        verbose: Show full build logs.
        quiet: Minimal output.

    Returns:
        Container name (str) ready for attachment.

    Raises:
        typer.Exit: On errors (missing path, Docker unavailable, etc.)
    """
    # Resolve project path (default to current directory)
    if path is None:
        project_path = Path.cwd()
    else:
        project_path = Path(path).resolve()

    # Validate project path exists
    if not project_path.exists():
        print(f"Error: Project path does not exist: {project_path}", file=sys.stderr)
        raise typer.Exit(1)

    if not project_path.is_dir():
        print(
            f"Error: Project path is not a directory: {project_path}", file=sys.stderr
        )
        raise typer.Exit(1)

    # Ensure config is initialized
    ensure_config_initialized()

    # Load config
    try:
        config = load_config()
    except ValueError as e:
        print(f"Error: Invalid configuration: {e}", file=sys.stderr)
        raise typer.Exit(1)

    # Check Docker availability
    if not check_docker_available():
        print(
            "Error: Docker is not running. Please start Docker and try again.",
            file=sys.stderr,
        )
        raise typer.Exit(1)

    # Determine container name
    container_name = sanitize_container_name(str(project_path))

    # Check if rebuild is needed
    should_rebuild = rebuild or needs_rebuild() or not image_exists()

    if should_rebuild:
        if not quiet:
            if rebuild:
                print("Rebuilding image (--rebuild flag)...")
            elif not image_exists():
                print("Building image (first run)...")
            else:
                print("Dockerfile changed, rebuilding image...")

        build_image(get_dockerfile_path(), verbose=verbose)
        save_dockerfile_hash()
        cleanup_dangling_images()

    # Check container status
    container_status = get_container_status(container_name)

    if container_status == "running":
        # Container is already running - prompt user
        action = prompt_running_container()

        if action == "cancel":
            if not quiet:
                print("Cancelled.")
            raise typer.Exit(0)
        elif action == "attach":
            # Return container name for caller to attach
            return container_name
        elif action == "restart":
            if not quiet:
                print(f"Restarting {container_name}...")
            stop_container(container_name)
            remove_container(container_name)
            container_status = "not-found"

    elif container_status in ("exited", "created"):
        # Container exists but not running - remove and recreate
        if not quiet:
            print(f"Removing stopped container {container_name}...")
        remove_container(container_name)
        container_status = "not-found"

    # Create new container if needed
    if container_status == "not-found":
        # Collect environment variables
        env_vars = collect_env_vars(project_path, env, config)

        # Assemble mounts
        extra_mounts = get_extra_mounts(config)
        mounts = assemble_mounts(project_path, extra_mounts)

        # Get shell from config
        shell = config.get("container", {}).get("shell", "/bin/bash")

        # Create and start container
        if not quiet:
            print(f"Creating container {container_name}...")
        create_container(
            name=container_name,
            image="occ:latest",
            mounts=mounts,
            env_vars=env_vars,
            shell=shell,
        )
        start_container(container_name)

    return container_name


def run_container_logic(
    project_path: Path | None = None,
    rebuild: bool = False,
    env: list[str] | None = None,
    keep_alive: bool = False,
    verbose: bool = False,
    quiet: bool = False,
) -> None:
    """Launch a container for the given project.

    This is the core logic for the main command. Uses ensure_container_running()
    to handle container lifecycle, then attaches with opencode.
    """
    # Use helper to ensure container is running
    container_name = ensure_container_running(
        path=project_path,
        rebuild=rebuild,
        env=env,
        verbose=verbose,
        quiet=quiet,
    )

    # Attach to container with opencode (default command)
    if not quiet:
        print(f"Attaching to {container_name}...")
    attach_to_container(container_name)

    # Handle stop on exit behavior
    config = load_config()
    stop_on_exit = config.get("container", {}).get("stop_on_exit", True)
    if stop_on_exit and not keep_alive:
        if not quiet:
            print(f"Stopping container {container_name}...")
        stop_container(container_name)
        remove_container(container_name)


# Create the main Typer app without the positional argument issue
# by using Click's group features directly

app = typer.Typer(
    name="occ",
    help="OpenCode Container CLI - Ephemeral development containers pre-loaded with OpenCode.",
    no_args_is_help=False,
)

# Config subcommand group
config_app = typer.Typer(
    name="config",
    help="Manage occ configuration.",
    invoke_without_command=True,
)
app.add_typer(config_app, name="config")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option(
            "--path",
            "-p",
            help="Project directory path (defaults to current directory).",
        ),
    ] = None,
    rebuild: Annotated[
        bool,
        typer.Option(
            "--rebuild",
            help="Force rebuild of container image.",
        ),
    ] = False,
    env: Annotated[
        Optional[list[str]],
        typer.Option(
            "--env",
            "-e",
            help="Pass environment variable (VAR=value), repeatable.",
        ),
    ] = None,
    keep_alive: Annotated[
        bool,
        typer.Option(
            "--keep-alive",
            help="Keep container running after shell exit.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Verbose output (show full build logs).",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Minimal output.",
        ),
    ] = False,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """OpenCode Container CLI - launch containers and start opencode.

    Running 'occ' launches a container for the current directory and
    starts opencode automatically. Use 'occ shell' for bash access.

    Examples:
        occ                  # Launch container and start opencode
        occ -p ~/myproject   # Launch opencode in ~/myproject
        occ --rebuild        # Force rebuild and launch
        occ shell            # Bash shell for current directory
        occ shell -p ~/proj  # Bash shell for ~/proj
        occ status           # List running containers
        occ stop             # Stop container for current directory
    """
    # If no subcommand was invoked, launch container and start opencode
    if ctx.invoked_subcommand is None:
        run_container_logic(
            project_path=path,
            rebuild=rebuild,
            env=env,
            keep_alive=keep_alive,
            verbose=verbose,
            quiet=quiet,
        )


@app.command()
def status() -> None:
    """List running occ containers."""
    ensure_config_initialized()
    require_docker()
    containers = list_occ_containers()

    if not containers:
        print("No occ containers running.")
        return

    # Print table header
    print(f"{'NAME':<25} {'PROJECT':<20} {'STATUS':<12} {'UPTIME':<10}")
    print("-" * 70)

    for c in containers:
        name = c.get("name", "")
        project = c.get("project", "")
        container_status = c.get("status", "")
        uptime = c.get("uptime", "")

        print(f"{name:<25} {project:<20} {container_status:<12} {uptime:<10}")


@app.command()
def shell(
    path: Annotated[
        Optional[Path],
        typer.Option(
            "--path",
            "-p",
            help="Project directory path (defaults to current directory).",
        ),
    ] = None,
    rebuild: Annotated[
        bool,
        typer.Option(
            "--rebuild",
            help="Force rebuild of container image.",
        ),
    ] = False,
    env: Annotated[
        Optional[list[str]],
        typer.Option(
            "--env",
            "-e",
            help="Pass environment variable (VAR=value), repeatable.",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Verbose output (show full build logs).",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Minimal output.",
        ),
    ] = False,
) -> None:
    """Launch a bash shell in an occ container.

    Creates the container if it doesn't exist. Use this when you need
    direct shell access instead of opencode.

    Examples:
        occ shell                  # Bash shell for current directory
        occ shell -p ~/myproject   # Bash shell for ~/myproject
        occ shell --rebuild        # Force rebuild, then bash shell
    """
    # Use helper to ensure container is running
    container_name = ensure_container_running(
        path=path,
        rebuild=rebuild,
        env=env,
        verbose=verbose,
        quiet=quiet,
    )

    # Attach with bash
    if not quiet:
        print(f"Attaching to {container_name} (bash)...")
    attach_to_container(container_name, command="/bin/bash")

    # Handle stop on exit (respects config)
    config = load_config()
    stop_on_exit = config.get("container", {}).get("stop_on_exit", True)
    if stop_on_exit:
        if not quiet:
            print(f"Stopping container {container_name}...")
        stop_container(container_name)
        remove_container(container_name)


@app.command()
def stop(
    project: Annotated[
        Optional[str],
        typer.Argument(help="Project name or container name (without occ- prefix)"),
    ] = None,
    all_containers: Annotated[
        bool,
        typer.Option("--all", "-a", help="Stop all occ containers"),
    ] = False,
) -> None:
    """Stop an occ container."""
    ensure_config_initialized()
    require_docker()

    if all_containers:
        # Stop all occ containers
        containers = list_occ_containers()
        if not containers:
            print("No occ containers to stop.")
            return

        stopped_count = 0
        for c in containers:
            name = c.get("name", "")
            if name:
                print(f"Stopping {name}...")
                stop_container(name)
                remove_container(name)
                stopped_count += 1

        print(f"Stopped {stopped_count} container(s).")
        return

    container_name = resolve_container_name(project)
    container_status = get_container_status(container_name)

    if container_status == "not-found":
        print(f"Error: Container '{container_name}' not found.", file=sys.stderr)
        raise typer.Exit(1)

    print(f"Stopping {container_name}...")
    stop_container(container_name)
    remove_container(container_name)
    print(f"Container '{container_name}' stopped and removed.")


# Config subcommand implementations


@config_app.callback(invoke_without_command=True)
def config_main(ctx: typer.Context) -> None:
    """Show config directory path if no subcommand given."""
    # Ensure config is initialized
    ensure_config_initialized()

    # If no subcommand was invoked, show config info
    if ctx.invoked_subcommand is None:
        print(f"Configuration directory: {CONFIG_DIR}")
        print(f"Config file: {get_config_path()}")
        print(f"Dockerfile: {get_dockerfile_path()}")
        print()
        print("Commands:")
        print("  occ config edit       - Edit config.toml in your editor")
        print("  occ config dockerfile - Edit Dockerfile in your editor")
        print("  occ config reset      - Reset configuration to defaults")


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


def _open_in_editor(file_path: Path) -> None:
    """Open a file in the user's editor.

    Args:
        file_path: Path to the file to edit.

    Raises:
        typer.Exit: If no editor is found or editor fails to open.
    """
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
        print(f"Or edit the file directly at: {file_path}")
        raise typer.Exit(1)

    # Open editor
    try:
        subprocess.run([editor, str(file_path)])
    except Exception as e:
        print(f"Error opening editor: {e}", file=sys.stderr)
        print(f"Edit the file directly at: {file_path}")
        raise typer.Exit(1)


@config_app.command("edit")
def config_edit() -> None:
    """Open config.toml in your editor."""
    ensure_config_initialized()
    _open_in_editor(get_config_path())


@config_app.command("dockerfile")
def config_dockerfile() -> None:
    """Open Dockerfile in your editor."""
    ensure_config_initialized()
    _open_in_editor(get_dockerfile_path())


if __name__ == "__main__":
    app()
