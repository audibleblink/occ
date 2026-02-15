"""Docker integration for occ.

This module handles all Docker operations including:
- Image building
- Container lifecycle management
- Status reporting
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound

if TYPE_CHECKING:
    from docker import DockerClient
    from docker.models.containers import Container


# Error messages
DOCKER_NOT_RUNNING_MSG = """
Docker daemon is not running.

To start Docker:
  - macOS: Open Docker Desktop application
  - Linux: Run 'sudo systemctl start docker'

Install Docker:
  - macOS: https://docs.docker.com/desktop/install/mac-install/
  - Linux: https://docs.docker.com/engine/install/
"""

DOCKER_PERMISSION_MSG = """
Permission denied when connecting to Docker.

To fix this:
  - macOS: Ensure Docker Desktop is running
  - Linux: Add your user to the docker group:
      sudo usermod -aG docker $USER
      # Then log out and log back in
"""


def _find_docker_socket() -> str | None:
    """Find the Docker socket path.

    Checks common locations for Docker socket including:
    - Default /var/run/docker.sock
    - Colima socket at ~/.config/colima/default/docker.sock
    - Docker Desktop socket at ~/.docker/run/docker.sock

    Returns:
        Socket URL if found, None otherwise.
    """
    socket_paths = [
        "/var/run/docker.sock",
        str(Path.home() / ".config" / "colima" / "default" / "docker.sock"),
        str(Path.home() / ".docker" / "run" / "docker.sock"),
        str(Path.home() / ".colima" / "default" / "docker.sock"),
    ]

    for socket_path in socket_paths:
        if Path(socket_path).exists():
            return f"unix://{socket_path}"

    return None


def _try_connect() -> DockerClient | None:
    """Attempt to connect to Docker daemon.

    Tries connecting via environment first, then searches for socket files.
    Sets DOCKER_HOST environment variable on successful socket connection.

    Returns:
        DockerClient if connection successful, None otherwise.
    """
    import os

    # First try from environment
    try:
        client = docker.from_env()
        client.ping()
        return client
    except DockerException:
        pass

    # Try to find socket and connect directly
    socket_url = _find_docker_socket()
    if socket_url:
        try:
            client = docker.DockerClient(base_url=socket_url)
            client.ping()
            # Set DOCKER_HOST for subprocess calls (like docker exec)
            os.environ["DOCKER_HOST"] = socket_url
            return client
        except DockerException:
            pass

    return None


def get_client() -> DockerClient:
    """Get Docker client, raise helpful error if Docker not available.

    Returns:
        DockerClient instance.

    Raises:
        SystemExit: If Docker daemon is not running or permission denied.
    """
    client = _try_connect()
    if client:
        return client

    # If we get here, Docker is not available
    # Try one more time to get a more specific error
    try:
        client = docker.from_env()
        client.ping()
        return client
    except DockerException as e:
        error_str = str(e).lower()
        if "permission denied" in error_str:
            print(DOCKER_PERMISSION_MSG, file=sys.stderr)
            sys.exit(1)
        elif "connection refused" in error_str or "not running" in error_str:
            print(DOCKER_NOT_RUNNING_MSG, file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Docker error: {e}", file=sys.stderr)
            sys.exit(1)


def check_docker_available() -> bool:
    """Verify Docker daemon is running.

    Returns:
        True if Docker is available and running, False otherwise.
    """
    return _try_connect() is not None


def build_image(
    dockerfile_path: Path, tag: str = "occ:latest", verbose: bool = False
) -> None:
    """Build image from Dockerfile, show progress.

    Args:
        dockerfile_path: Path to the Dockerfile.
        tag: Image tag (default: occ:latest).
        verbose: If True, show full build output. If False, show single updating line.

    Raises:
        SystemExit: If build fails.
    """
    client = get_client()
    dockerfile_dir = dockerfile_path.parent

    try:
        # Build using low-level API for streaming output
        print(f"Building image {tag}...")

        # Use build with decode=True for streaming
        build_logs = client.api.build(
            path=str(dockerfile_dir),
            dockerfile=dockerfile_path.name,
            tag=tag,
            rm=True,  # Remove intermediate containers
            decode=True,
        )

        last_step = ""
        for log in build_logs:
            if "stream" in log:
                line = log["stream"].strip()
                if line:
                    if verbose:
                        print(line)
                    else:
                        # Extract step info for single-line progress
                        if line.startswith("Step ") or line.startswith("---> "):
                            last_step = line[:60]
                            # Print with carriage return for updating line
                            print(f"\r{last_step:<70}", end="", flush=True)
            elif "error" in log:
                print(f"\nBuild error: {log['error']}", file=sys.stderr)
                sys.exit(1)
            elif "errorDetail" in log:
                detail = log["errorDetail"].get("message", "Unknown error")
                print(f"\nBuild error: {detail}", file=sys.stderr)
                sys.exit(1)

        # Clear the line and print success
        if not verbose:
            print(f"\r{'Build complete!':<70}")
        else:
            print("Build complete!")

    except APIError as e:
        print(f"\nDocker API error during build: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nBuild failed: {e}", file=sys.stderr)
        sys.exit(1)


def image_exists(tag: str = "occ:latest") -> bool:
    """Check if image exists.

    Args:
        tag: Image tag to check.

    Returns:
        True if image exists, False otherwise.
    """
    client = get_client()
    try:
        client.images.get(tag)
        return True
    except ImageNotFound:
        return False


def create_container(
    name: str,
    image: str,
    mounts: list[dict],
    env_vars: dict,
    shell: str,
) -> None:
    """Create container with mounts and env vars.

    Args:
        name: Container name.
        image: Image tag to use.
        mounts: List of mount dicts with source, target, and optional mode.
            Format: [{"source": "/path", "target": "/container/path", "mode": "rw"}]
        env_vars: Environment variables dict.
        shell: Shell to use (e.g., /bin/bash).

    Raises:
        SystemExit: If container creation fails.
    """
    client = get_client()

    # Convert mounts to docker format
    volumes = {}
    for m in mounts:
        source = m["source"]
        target = m["target"]
        mode = m.get("mode", "rw")
        volumes[source] = {"bind": target, "mode": mode}

    try:
        client.containers.create(
            image=image,
            name=name,
            volumes=volumes,
            environment=env_vars,
            working_dir="/workspace",
            stdin_open=True,
            tty=True,
            detach=True,
        )
    except APIError as e:
        if "Conflict" in str(e):
            print(
                f"Container '{name}' already exists. Use 'occ stop {name}' to remove it.",
                file=sys.stderr,
            )
        else:
            print(f"Failed to create container: {e}", file=sys.stderr)
        sys.exit(1)


def start_container(name: str) -> None:
    """Start existing container.

    Args:
        name: Container name.

    Raises:
        SystemExit: If container doesn't exist or start fails.
    """
    client = get_client()
    try:
        container = client.containers.get(name)
        container.start()
    except NotFound:
        print(f"Container '{name}' not found.", file=sys.stderr)
        sys.exit(1)
    except APIError as e:
        print(f"Failed to start container: {e}", file=sys.stderr)
        sys.exit(1)


def attach_to_container(name: str, command: str = "opencode") -> None:
    """Attach to container and run a command interactively.

    Uses subprocess to run docker exec -it for proper TTY handling.

    Args:
        name: Container name.
        command: Command to run in the container (default: opencode).

    Raises:
        SystemExit: If attach fails.
    """
    try:
        # Use subprocess for interactive TTY
        result = subprocess.run(
            ["docker", "exec", "-it", name, command],
            check=False,
        )
        # Exit code from the container shell
        if result.returncode != 0 and result.returncode != 130:
            # 130 is Ctrl+C which is normal
            sys.exit(result.returncode)
    except FileNotFoundError:
        print("docker command not found. Is Docker installed?", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        # Normal exit via Ctrl+C
        pass


def stop_container(name: str) -> None:
    """Stop container.

    Args:
        name: Container name.
    """
    client = get_client()
    try:
        container = client.containers.get(name)
        if container.status == "running":
            container.stop(timeout=5)
    except NotFound:
        # Container doesn't exist, that's fine
        pass
    except APIError as e:
        print(f"Failed to stop container: {e}", file=sys.stderr)


def remove_container(name: str) -> None:
    """Remove container.

    Args:
        name: Container name.
    """
    client = get_client()
    try:
        container = client.containers.get(name)
        container.remove(force=True)
    except NotFound:
        # Container doesn't exist, that's fine
        pass
    except APIError as e:
        print(f"Failed to remove container: {e}", file=sys.stderr)


def list_occ_containers() -> list[dict]:
    """List containers with occ- prefix.

    Returns:
        List of container info dicts with keys: name, status, project, uptime.
    """
    client = get_client()

    try:
        # List all containers (including stopped)
        containers = client.containers.list(all=True, filters={"name": "occ-"})

        result = []
        for container in containers:
            name = container.name
            status = container.status

            # Extract project name from container name (remove occ- prefix)
            project = name[4:] if name.startswith("occ-") else name

            # Calculate uptime for running containers
            uptime = ""
            if status == "running":
                # Get container start time
                attrs = container.attrs
                started_at = attrs.get("State", {}).get("StartedAt", "")
                if started_at:
                    try:
                        # Parse ISO format timestamp
                        start_time = datetime.fromisoformat(
                            started_at.replace("Z", "+00:00")
                        )
                        now = datetime.now(timezone.utc)
                        delta = now - start_time
                        uptime = _format_duration(delta.total_seconds())
                    except (ValueError, TypeError):
                        uptime = "unknown"

            result.append(
                {
                    "name": name,
                    "status": status,
                    "project": project,
                    "uptime": uptime,
                }
            )

        return result

    except APIError:
        return []


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable format.

    Args:
        seconds: Duration in seconds.

    Returns:
        Human-readable duration string.
    """
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"


def get_container_status(name: str) -> str:
    """Get container status.

    Args:
        name: Container name.

    Returns:
        Status string: running/exited/created/not-found.
    """
    client = get_client()
    try:
        container = client.containers.get(name)
        return container.status
    except (NotFound, APIError):
        return "not-found"


def cleanup_dangling_images() -> None:
    """Remove old untagged occ images."""
    client = get_client()
    try:
        # Find dangling images (untagged)
        dangling = client.images.list(filters={"dangling": True})

        for image in dangling:
            # Check if it's related to occ builds
            try:
                client.images.remove(image.id)
            except APIError:
                # Image might be in use, skip
                pass

    except APIError:
        # Cleanup is best-effort
        pass


def sanitize_container_name(project_path: str) -> str:
    """Convert path to valid container name.

    Args:
        project_path: Project directory path.

    Returns:
        Valid container name with occ- prefix.

    Example:
        /Users/me/Code/My Project -> occ-my-project
    """
    # Get basename of path
    name = Path(project_path).name

    # Lowercase and replace non-alphanumeric with hyphens
    name = re.sub(r"[^a-z0-9]+", "-", name.lower())

    # Remove leading/trailing hyphens
    name = name.strip("-")

    # Ensure name is not empty
    if not name:
        name = "project"

    return f"occ-{name}"


def get_default_mounts(project_path: Path) -> list[dict]:
    """Get default mount points for a project.

    This includes:
    - Project directory -> /workspace (rw)
    - OpenCode config directories (ro):
      - ~/.config/opencode -> /root/.config/opencode
      - ~/.local/share/opencode -> /root/.local/share/opencode
      - ~/.local/state/opencode -> /root/.local/state/opencode

    Args:
        project_path: Path to the project directory.

    Returns:
        List of mount dicts.
    """
    mounts = []

    # Project directory mount
    mounts.append(
        {
            "source": str(project_path.resolve()),
            "target": "/workspace",
            "mode": "rw",
        }
    )

    # OpenCode config mounts (read-only)
    opencode_paths = [
        ("~/.config/opencode", "/root/.config/opencode"),
        ("~/.local/share/opencode", "/root/.local/share/opencode"),
        ("~/.local/state/opencode", "/root/.local/state/opencode"),
    ]

    for host_path, container_path in opencode_paths:
        expanded = Path(host_path).expanduser()
        if expanded.exists():
            mounts.append(
                {
                    "source": str(expanded),
                    "target": container_path,
                    "mode": "ro",
                }
            )

    return mounts


def assemble_mounts(
    project_path: Path, extra_mounts: list[dict] | None = None
) -> list[dict]:
    """Assemble all mount points for container creation.

    Combines default mounts with extra mounts from config.

    Args:
        project_path: Path to the project directory.
        extra_mounts: Additional mounts from config (optional).

    Returns:
        Complete list of mount dicts.
    """
    mounts = get_default_mounts(project_path)

    if extra_mounts:
        # Expand paths in extra mounts and add them
        for mount in extra_mounts:
            expanded_mount = mount.copy()
            if "source" in expanded_mount:
                expanded_mount["source"] = str(
                    Path(expanded_mount["source"]).expanduser()
                )
            mounts.append(expanded_mount)

    return mounts
