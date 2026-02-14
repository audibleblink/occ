"""CLI entry point for occ."""

import typer

from occ import __version__

app = typer.Typer(
    name="occ",
    help="OpenCode Container CLI - Ephemeral development containers pre-loaded with OpenCode.",
    no_args_is_help=True,
)


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


if __name__ == "__main__":
    app()
