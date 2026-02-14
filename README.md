# occ - OpenCode Container CLI

Ephemeral development containers pre-loaded with OpenCode and developer tools.

## Overview

`occ` is a CLI tool that launches isolated development containers with:

- **Project mounting** at `/workspace` with correct file ownership
- **Environment variable passthrough** via allowlist, `.env` files, and CLI flags
- **Automatic Dockerfile change detection** and rebuilds
- **Multi-container support** for parallel projects

One command spins up a fully-equipped workspace. Containers are automatically cleaned up when you exit.

```bash
occ run ~/Code/myproject    # Launch container with your project
```

## Requirements

- **Python 3.12+**
- **Docker Desktop** or **Docker Engine**

## Installation

Install using `uv tool`:

```bash
uv tool install git+https://github.com/yourorg/occ.git
```

Or install from local source:

```bash
git clone https://github.com/yourorg/occ.git
cd occ
uv tool install .
```

Or for development:

```bash
git clone https://github.com/yourorg/occ.git
cd occ
uv pip install -e .
```

Verify installation:

```bash
occ --version   # Should print: 1.0.0
occ --help
```

## Quick Start

```bash
# Launch container for current directory
occ run

# Launch container for a specific project
occ run ~/Code/myproject

# Force rebuild if Dockerfile changed
occ run --rebuild

# Pass extra environment variables
occ run --env MY_API_KEY=secret ~/Code/myproject

# Keep container running after exit (for reattaching later)
occ run --keep-alive
```

## Command Reference

### Main Commands

| Command | Description |
|---------|-------------|
| `occ run [PATH]` | Launch container for a project directory |
| `occ status` | List running occ containers |
| `occ shell [PROJECT]` | Attach to a running container |
| `occ stop [PROJECT]` | Stop a container |
| `occ stop --all` | Stop all occ containers |
| `occ config` | Show configuration directory |
| `occ config edit` | Edit config.toml in your editor |
| `occ config reset` | Reset configuration to defaults |

### Options for `occ run`

| Option | Description |
|--------|-------------|
| `--rebuild` | Force rebuild of container image |
| `--env`, `-e` | Pass env var (VAR=value), repeatable |
| `--keep-alive` | Keep container running after shell exit |
| `--verbose`, `-v` | Verbose output |
| `--quiet`, `-q` | Minimal output |

### Examples

```bash
# Start a container for the current directory
occ run

# Work on a specific project
occ run ~/Code/my-awesome-project

# Pass multiple environment variables
occ run -e API_KEY=secret -e DEBUG=1 ~/Code/project

# Rebuild after modifying the Dockerfile
occ run --rebuild

# Check running containers
occ status

# Attach to a running container
occ shell myproject

# Stop a specific container
occ stop myproject

# Stop all containers
occ stop --all
```

## Configuration

Configuration is stored in `~/.config/occ/`:

```
~/.config/occ/
├── config.toml      # Main configuration file
└── Dockerfile       # Container image definition
```

On first run, default configuration files are automatically created.

### config.toml

```toml
[container]
stop_on_exit = true      # Auto-stop container when shell exits
shell = "/bin/bash"      # Shell to use in container

[mounts]
# Extra mounts (in addition to project mount)
extra = []

[env]
# Environment variables to pass through from host
allowlist = [
    "LANG",
    "LC_ALL",
    "EDITOR",
    "TERM",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
]

# Load .env file from project directory
load_dotenv = true
```

### Customizing the Dockerfile

Edit `~/.config/occ/Dockerfile` to customize the container image:

```bash
occ config edit    # Opens config.toml (edit Dockerfile directly)
# or
$EDITOR ~/.config/occ/Dockerfile
```

After making changes, the next `occ run` will automatically detect the change and rebuild.

### Environment Variable Priority

Environment variables are collected in this order (later overrides earlier):

1. Host allowlist (from config.toml)
2. CLI `--env` flags
3. Project `.env` file
4. Implicit vars (`HOST_UID`, `HOST_GID`)

## How It Works

1. **First Run**: Creates `~/.config/occ/` with default Dockerfile and config
2. **Image Build**: Builds Docker image from `~/.config/occ/Dockerfile`
3. **Container Creation**: Creates container with project mounted at `/workspace`
4. **Shell Attach**: Attaches interactive shell to the container
5. **Cleanup**: Stops and removes container on exit (unless `--keep-alive`)

Container names are derived from project paths (e.g., `occ-myproject`).

## Troubleshooting

### Docker not running

```
Error: Docker is not running. Please start Docker and try again.
```

Start Docker Desktop or the Docker daemon.

### Project path does not exist

```
Error: Project path does not exist: /path/to/project
```

Verify the path exists and is spelled correctly.

### Container already running

When running `occ run` for a project that has a running container, you'll be prompted:

```
Container is running. [A]ttach / [R]estart / [C]ancel?
```

- **A** - Attach to the existing container
- **R** - Stop and recreate the container
- **C** - Cancel

### Reset to defaults

If configuration gets corrupted:

```bash
occ config reset
```

## License

MIT
