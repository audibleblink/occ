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
occ ~/Code/myproject    # Launch container with your project
```

## Requirements

- **Python 3.12+**
- **Docker or Colima Engine**

## Installation

Install using `uv tool`:

```bash
uv tool install git+https://github.com/audibleblink/occ.git
```

## Quick Start

```bash
# Launch an opencode container for current directory
occ 

# Launch container for a specific project
occ ~/Code/myproject

# Pass extra environment variables
occ --env MY_API_KEY=secret ~/Code/myproject

```

## Command Reference

### Main Commands

| Command | Description |
|---------|-------------|
| `occ [PATH]` | Launch container for a project directory |
| `occ status` | List running occ containers |
| `occ shell [PROJECT]` | Attach to a running container |
| `occ stop [PROJECT]` | Stop a container |
| `occ stop --all` | Stop all occ containers |
| `occ config` | Show configuration directory |
| `occ config edit` | Edit config.toml in your editor |
| `occ config dockerfile` | Edit Dockerfile in your editor |
| `occ config reset` | Reset configuration to defaults |

### Options for `occ [PATH]`

| Option | Description |
|--------|-------------|
| `--rebuild` | Force rebuild of container image |
| `--env`, `-e` | Pass env var (VAR=value), repeatable |
| `--keep-alive` | Keep container running after shell exit |
| `--verbose`, `-v` | Verbose output (show full build logs) |
| `--quiet`, `-q` | Minimal output |
| `--version`, `-V` | Show version and exit |


## Configuration

Configuration is stored in `~/.config/occ/`:

```
~/.config/occ/
├── config.toml      # Main configuration file
└── Dockerfile       # Container image definition
```

On first run, default configuration files are automatically copied from the package.

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

After the initial run,
edit `~/.config/occ/Dockerfile` to customize the container image:

```bash
occ config dockerfile    # Opens Dockerfile in your editor
```

After making changes, the next `occ` will automatically detect the change and rebuild.

### Environment Variable Priority

Environment variables are collected in this order (higher priority overrides lower):

1. **Lowest**: Host env vars matching allowlist (from config.toml)
2. **Middle**: Project `.env` file (if `load_dotenv = true`)
3. **Highest**: CLI `--env` flags

## How It Works

1. **First Run**: Creates `~/.config/occ/` with default Dockerfile and config
2. **Image Build**: Builds Docker image from `~/.config/occ/Dockerfile`
3. **Container Creation**: Creates container with project mounted at `/workspace`
4. **Shell Attach**: Attaches interactive shell to the container
5. **Cleanup**: Stops and removes container on exit (unless `--keep-alive`)

Container names are derived from project paths (e.g., `occ-myproject`).

### Reset to defaults

If configuration gets corrupted:

```bash
occ config reset
```
