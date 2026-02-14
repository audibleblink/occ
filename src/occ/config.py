"""Configuration management for occ.

This module handles:
- Config directory initialization
- TOML configuration parsing
- Dockerfile hash tracking for rebuild detection
"""

from __future__ import annotations

import hashlib
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

# Key constants
CONFIG_DIR = Path.home() / ".config" / "occ"

# Required config keys for validation
REQUIRED_SECTIONS = ["container", "mounts", "env"]
REQUIRED_CONTAINER_KEYS = ["stop_on_exit", "shell"]
REQUIRED_ENV_KEYS = ["allowlist", "load_dotenv"]


def get_config_path() -> Path:
    """Return path to config.toml."""
    return CONFIG_DIR / "config.toml"


def get_dockerfile_path() -> Path:
    """Return path to Dockerfile."""
    return CONFIG_DIR / "Dockerfile"


def _get_hash_path() -> Path:
    """Return path to .dockerfile-hash file."""
    return CONFIG_DIR / ".dockerfile-hash"


def _get_default_resource(name: str) -> str:
    """Get content of a default resource file.

    Args:
        name: Name of the resource file (e.g., "Dockerfile", "config.toml")

    Returns:
        Content of the resource file as string.
    """
    with resources.as_file(resources.files("occ.resources").joinpath(name)) as f:
        return f.read_text()


def ensure_config_initialized() -> bool:
    """Create config dir and copy defaults if missing.

    Returns:
        True if configuration was initialized (first run), False if already existed.
    """
    initialized = False

    # Create config directory if it doesn't exist
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        initialized = True

    # Copy default config.toml if missing
    config_path = get_config_path()
    if not config_path.exists():
        default_config = _get_default_resource("config.toml")
        config_path.write_text(default_config)
        initialized = True

    # Copy default Dockerfile if missing
    dockerfile_path = get_dockerfile_path()
    if not dockerfile_path.exists():
        default_dockerfile = _get_default_resource("Dockerfile")
        dockerfile_path.write_text(default_dockerfile)
        initialized = True

    if initialized:
        print(f"Initialized occ configuration at {CONFIG_DIR}/")

    return initialized


def load_config() -> dict[str, Any]:
    """Parse and return config.toml using tomllib.

    This function ensures configuration is initialized before loading.

    Returns:
        Parsed TOML configuration as a dictionary.

    Raises:
        ValueError: If configuration is missing required keys.
    """
    ensure_config_initialized()

    config_path = get_config_path()
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    _validate_config(config)
    return config


def _validate_config(config: dict[str, Any]) -> None:
    """Validate that configuration has all required keys.

    Args:
        config: Parsed configuration dictionary.

    Raises:
        ValueError: If required keys are missing.
    """
    # Check required sections
    for section in REQUIRED_SECTIONS:
        if section not in config:
            raise ValueError(f"Missing required config section: [{section}]")

    # Check container keys
    for key in REQUIRED_CONTAINER_KEYS:
        if key not in config["container"]:
            raise ValueError(f"Missing required key in [container]: {key}")

    # Check env keys
    for key in REQUIRED_ENV_KEYS:
        if key not in config["env"]:
            raise ValueError(f"Missing required key in [env]: {key}")


def needs_rebuild() -> bool:
    """Compare current Dockerfile hash with stored hash.

    Returns:
        True if Dockerfile has changed or no hash file exists, False otherwise.
    """
    ensure_config_initialized()

    dockerfile_path = get_dockerfile_path()
    hash_path = _get_hash_path()

    if not dockerfile_path.exists():
        return True

    current_hash = hashlib.sha256(dockerfile_path.read_bytes()).hexdigest()
    stored_hash = hash_path.read_text().strip() if hash_path.exists() else ""

    return current_hash != stored_hash


def save_dockerfile_hash() -> None:
    """Save current Dockerfile hash to .dockerfile-hash file."""
    ensure_config_initialized()

    dockerfile_path = get_dockerfile_path()
    hash_path = _get_hash_path()

    if dockerfile_path.exists():
        current_hash = hashlib.sha256(dockerfile_path.read_bytes()).hexdigest()
        hash_path.write_text(current_hash)


def reset_config() -> None:
    """Reset Dockerfile and config.toml to defaults."""
    # Get default content
    default_config = _get_default_resource("config.toml")
    default_dockerfile = _get_default_resource("Dockerfile")

    # Ensure directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Write defaults
    get_config_path().write_text(default_config)
    get_dockerfile_path().write_text(default_dockerfile)

    # Remove hash file so rebuild will be triggered
    hash_path = _get_hash_path()
    if hash_path.exists():
        hash_path.unlink()


def expand_path(path: str) -> Path:
    """Expand ~ in paths.

    Args:
        path: Path string that may contain ~ for home directory.

    Returns:
        Expanded Path object.
    """
    return Path(path).expanduser()


def get_extra_mounts(config: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Get extra mounts from config with paths expanded.

    Args:
        config: Optional pre-loaded config. If None, will load config.

    Returns:
        List of mount dictionaries with expanded paths.
    """
    if config is None:
        config = load_config()

    extra = config.get("mounts", {}).get("extra", [])
    expanded = []

    for mount in extra:
        if isinstance(mount, str):
            # Simple path string - treat as read-only mount to same location
            expanded_path = str(expand_path(mount))
            expanded.append(
                {"source": expanded_path, "target": expanded_path, "mode": "ro"}
            )
        elif isinstance(mount, dict):
            # Full mount specification
            mount_copy = mount.copy()
            if "source" in mount_copy:
                mount_copy["source"] = str(expand_path(mount_copy["source"]))
            if "target" in mount_copy:
                mount_copy["target"] = str(expand_path(mount_copy["target"]))
            expanded.append(mount_copy)

    return expanded
