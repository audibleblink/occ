# PRD: `occ` - OpenCode Container CLI

**Version:** 1.0  
**Date:** 2026-02-14  
**Status:** Draft  

---

## Overview

Convert the existing `occ` bash script into a Python package installable via `uv tool install`. The tool launches containerized development environments with OpenCode configurations pre-mounted, providing a consistent and reproducible development experience.

---

## Problem Statement

The current bash-based `occ` tool has limitations:
- Difficult to extend and maintain
- No cross-platform consistency
- Manual installation process
- No automatic change detection for Dockerfile modifications

---

## Goals

1. **Zero-friction installation** via `uv tool install git+https://github.com/...`
2. **Auto-initialize** configuration on first run (no manual setup)
3. **Auto-detect Dockerfile changes** and rebuild when necessary
4. **Support multiple concurrent containers** named by project
5. **Configurable behavior** via TOML config file and CLI flags

---

## Non-Goals (MVP)

- Tailscale integration (deferred to future version)
- Apple container CLI support (Docker only)
- Test suite (deferred)
- Windows support

---

## User Stories

### Primary Flow
```bash
# Install once
$ uv tool install git+https://github.com/yourorg/occ

# Run on any project
$ occ ~/Code/my-project
# First run: Initializes ~/.config/occ/, builds image, launches container
# Subsequent runs: Attaches or prompts if container already running
```

### Dockerfile Customization
```bash
$ vim ~/.config/occ/Dockerfile
$ occ ~/Code/my-project
# "Dockerfile changed, rebuilding image..."
```

### Managing Containers
```bash
$ occ status                    # List running occ containers
$ occ shell my-project          # Attach to running container
$ occ stop my-project           # Stop a container
$ occ config reset              # Reset Dockerfile to default
```

---

## Technical Specification

### Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.12+ | Modern features, type hints |
| CLI Framework | Typer | Type-hint driven, excellent UX |
| Docker Integration | docker-py (Docker SDK) | Official SDK, full API access |
| Env File Parsing | python-dotenv | Standard, well-maintained |
| Config Format | TOML | Python stdlib (tomllib), clean syntax |
| Package Manager | uv | Fast, modern Python tooling |

### Dependencies

```toml
[project]
dependencies = [
    "typer>=0.9.0",
    "docker>=7.0.0",
    "python-dotenv>=1.0.0",
]
```

### File Structure

```
occ/
├── pyproject.toml
├── README.md
├── .gitignore
└── src/
    └── occ/
        ├── __init__.py          # Version string
        ├── cli.py               # Typer app, command definitions
        ├── docker.py            # Docker SDK wrapper
        ├── env.py               # Env var collection logic
        ├── config.py            # Config management, paths, hash checking
        └── resources/
            ├── Dockerfile       # Embedded default Dockerfile
            └── config.toml      # Embedded default config
```

### Files to Remove (from existing repo)

| File | Reason |
|------|--------|
| `occ` (bash script) | Replaced by Python package |
| `install.sh` | Replaced by `uv tool install` |

### Files to Migrate

| From | To | Notes |
|------|-----|-------|
| `Dockerfile` | `src/occ/resources/Dockerfile` | Embedded in package |

---

## CLI Design

### Main Command

```bash
occ [OPTIONS] [PROJECT_PATH]
```

| Option | Description |
|--------|-------------|
| `PROJECT_PATH` | Path to project directory (default: current directory) |
| `--rebuild` | Force rebuild of container image |
| `--env VAR` | Pass additional env var (repeatable) |
| `--keep-alive` | Don't stop container on shell exit |
| `-v, --verbose` | Verbose output |
| `-q, --quiet` | Minimal output |

**Behavior when container already running:**
- Prompt user: `Container 'occ-my-project' is running. [A]ttach / [R]estart / [C]ancel?`

### Subcommands

| Command | Description |
|---------|-------------|
| `occ status` | List running occ containers (name, project path, image hash, uptime) |
| `occ shell [PROJECT]` | Attach to a running container |
| `occ stop [PROJECT]` | Stop a running container |
| `occ config` | Show config directory path |
| `occ config reset` | Reset Dockerfile and config to defaults |
| `occ config edit` | Open config file in $EDITOR |

---

## Configuration

### Config Directory Structure

```
~/.config/occ/
├── config.toml          # User configuration
├── Dockerfile           # Customizable Dockerfile
└── .dockerfile-hash     # SHA256 hash for change detection
```

### Default Config (`config.toml`)

```toml
[container]
# Stop container when shell exits (true) or keep running (false)
stop_on_exit = true
# Shell to use inside container
shell = "/bin/bash"

[mounts]
# Additional mount points (project dir always mounted at /workspace)
# Format: "host_path:container_path:mode" where mode is "rw" or "ro"
extra = []

[env]
# Environment variables to pass through from host
allowlist = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "MISTRAL_API_KEY",
]
# Load .env file from project directory
load_dotenv = true
```

### Auto-Initialization (Option C from proposal)

On first run:
1. Check if `~/.config/occ/` exists
2. If not, create directory and copy embedded `Dockerfile` and `config.toml`
3. Print: `Initialized occ configuration at ~/.config/occ/`

---

## Mount Points

### Default Mounts (Always Applied)

| Host Path | Container Path | Mode |
|-----------|----------------|------|
| `<PROJECT_PATH>` | `/workspace` | rw |
| `~/.config/opencode` | `/root/.config/opencode` | ro |
| `~/.local/share/opencode` | `/root/.local/share/opencode` | ro |
| `~/.local/state/opencode` | `/root/.local/state/opencode` | ro |

### User-Configurable Mounts

Via `config.toml`:
```toml
[mounts]
extra = [
    "~/.ssh:/root/.ssh:ro",
    "~/.gitconfig:/root/.gitconfig:ro",
]
```

---

## Docker Image Management

### Image Naming
- Tag: `occ:latest`
- On rebuild: Remove old dangling images to save disk space

### Change Detection

```python
def needs_rebuild() -> bool:
    dockerfile_path = CONFIG_DIR / "Dockerfile"
    hash_path = CONFIG_DIR / ".dockerfile-hash"
    
    current_hash = hashlib.sha256(dockerfile_path.read_bytes()).hexdigest()
    stored_hash = hash_path.read_text().strip() if hash_path.exists() else ""
    
    return current_hash != stored_hash

def save_hash():
    current_hash = hashlib.sha256(dockerfile_path.read_bytes()).hexdigest()
    hash_path.write_text(current_hash)
```

### Build Triggers
1. Image `occ:latest` doesn't exist
2. Dockerfile hash changed
3. `--rebuild` flag passed

---

## Container Naming

Containers are named based on project directory:
- Pattern: `occ-{sanitized_project_name}`
- Sanitization: lowercase, replace non-alphanumeric with hyphens
- Example: `~/Code/My Project` → `occ-my-project`

---

## Environment Variable Handling

### Priority (highest to lowest)
1. CLI `--env` flags
2. Project `.env` file (if `load_dotenv = true`)
3. Host env vars matching allowlist

### Default Allowlist
```python
DEFAULT_ALLOWLIST = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY", 
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "MISTRAL_API_KEY",
]
```

---

## Error Handling

### Docker Not Available
```
Error: Docker is not running or not installed.

To install Docker:
  macOS: https://docs.docker.com/desktop/install/mac-install/
  Linux: https://docs.docker.com/engine/install/

Then start Docker and run occ again.
```

### Project Path Doesn't Exist
```
Error: Project path '/path/to/project' does not exist.
```

### Permission Denied
```
Error: Cannot access Docker socket. 
Ensure your user is in the 'docker' group or Docker Desktop is running.
```

---

## Output Verbosity

### Default (no flags)
- Key status messages only
- Build progress (single line, updating)
- Errors

### Verbose (`-v`)
- All default output
- Mount point details
- Environment variables being passed
- Docker commands being executed

### Quiet (`-q`)
- Errors only
- No progress indicators

---

## Status Command Output

```bash
$ occ status
NAME              PROJECT                    IMAGE HASH    UPTIME
occ-my-project    /Users/me/Code/my-project  a1b2c3d4      2h 15m
occ-another       /Users/me/Code/another     a1b2c3d4      45m
```

---

## Success Metrics

1. Installation completes in < 30 seconds
2. First run (with image build) completes in < 5 minutes
3. Subsequent runs attach to shell in < 3 seconds
4. Zero manual configuration required for basic usage

---

## Future Enhancements (Post-MVP)

1. **Tailscale integration** - Mount Tailscale socket for network access
2. **Shell passthrough** - Option to use host shell instead of bash
3. **Multiple Dockerfiles** - Support for project-specific Dockerfiles
4. **Plugin system** - Allow custom pre/post hooks
5. **Test suite** - Unit and integration tests
6. **JSON output** - `--json` flag for scripting

---

## Open Questions

None - all questions resolved during PRD development.

---

## Appendix: Command Reference

```bash
# Launch container for project
occ ~/Code/project
occ .                           # Current directory
occ --rebuild ~/Code/project    # Force image rebuild
occ --env MY_VAR=value .        # Pass extra env var
occ --keep-alive .              # Don't stop on exit
occ -v .                        # Verbose output
occ -q .                        # Quiet mode

# Container management
occ status                      # List running containers
occ shell project-name          # Attach to running container
occ stop project-name           # Stop container
occ stop --all                  # Stop all occ containers

# Configuration
occ config                      # Show config path
occ config reset                # Reset to defaults
occ config edit                 # Open in $EDITOR
```
