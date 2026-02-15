"""Environment variable handling for occ.

This module handles:
- Collecting environment variables from various sources
- Allowlist filtering
- .env file parsing
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def collect_env_vars(
    project_path: Path,
    cli_env: list[str] | None,
    config: dict[str, Any],
) -> dict[str, str]:
    """Collect environment variables by priority.

    Priority order (highest to lowest):
    1. CLI --env flags
    2. Project .env file (if load_dotenv = true)
    3. Host env vars matching allowlist

    Args:
        project_path: Path to the project directory.
        cli_env: List of CLI env vars in "VAR=value" format.
        config: Loaded configuration dictionary.

    Returns:
        Dictionary of environment variables to pass to container.
    """
    env_vars: dict[str, str] = {}

    # 1. Start with host env vars matching allowlist (lowest priority)
    env_config = config.get("env", {})
    allowlist = env_config.get("allowlist", [])

    for var_name in allowlist:
        if var_name in os.environ:
            env_vars[var_name] = os.environ[var_name]

    # 2. Load from project .env file (middle priority)
    load_dotenv = env_config.get("load_dotenv", True)
    if load_dotenv:
        dotenv_path = project_path / ".env"
        if dotenv_path.exists():
            dotenv_vars = _parse_dotenv(dotenv_path)
            env_vars.update(dotenv_vars)

    # 3. CLI --env flags (highest priority)
    if cli_env:
        for env_item in cli_env:
            if "=" in env_item:
                key, value = env_item.split("=", 1)
                env_vars[key.strip()] = value.strip()
            else:
                # If no value, try to get from current environment
                if env_item in os.environ:
                    env_vars[env_item] = os.environ[env_item]

    return env_vars


def _parse_dotenv(dotenv_path: Path) -> dict[str, str]:
    """Parse a .env file into a dictionary.

    Handles:
    - KEY=value pairs
    - Comments (#)
    - Empty lines
    - Quoted values (single and double)
    - Values with = signs

    Args:
        dotenv_path: Path to the .env file.

    Returns:
        Dictionary of environment variables.
    """
    env_vars: dict[str, str] = {}

    try:
        with open(dotenv_path) as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Skip lines without =
                if "=" not in line:
                    continue

                # Split on first = only
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Skip empty keys
                if not key:
                    continue

                # Remove surrounding quotes from value
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]

                env_vars[key] = value

    except (OSError, IOError):
        # If we can't read the file, return empty dict
        pass

    return env_vars
