# occ - OpenCode Container

Ephemeral development containers pre-loaded with OpenCode and developer tools.

## Overview

`occ` is a CLI tool that launches isolated development containers with:

- **Project mounting** with correct file ownership
- **Environment variable passthrough** via allowlist, `.env` files, and flags
- **Multi-architecture support** (arm64 + amd64)

One command spins up a fully-equipped workspace. When you exit, the container is destroyed—no state accumulates.

```bash
occ ~/Code/myproject    # Launch container with your project
```

The container includes common dev tools: git, neovim, tmux, ripgrep, fzf, python, and more.

## Requirements

- **Python 3.12+**
- **Docker Desktop** / **Docker Engine**

## Installation

Install using `uv`:

```bash
uv tool install occ
```

Or install from source:

```bash
git clone https://github.com/yourorg/occ.git
cd occ
uv tool install .
```

Verify installation:

```bash
occ --help
occ --version
```

The first run will build the container image, which takes a few minutes.

## Usage

### Basic Commands

```bash
occ                         # Start bash shell in container
occ ~/Code/project          # Start OpenCode with project mounted at /workspace
occ --rebuild               # Force rebuild of the container image
occ --env MY_VAR ~/proj     # Pass additional environment variable
occ --no-tailscale          # Skip Tailscale setup (no TS_AUTHKEY required)
occ status                  # List running occ containers
occ config                  # Show config directory and contents
```

### Options Reference

| Option | Description |
|--------|-------------|
| `--rebuild` | Force rebuild of the container image, ignoring cache |
| `--env VAR` | Pass an additional environment variable (repeatable) |
| `--no-tailscale` | Skip Tailscale setup; does not require `TS_AUTHKEY` |
| `--help` | Print usage information |

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `occ status` | List running occ containers with name, status, and mounts |
| `occ config` | Show the config directory path and list its contents |

### Examples

**Start a quick bash session:**
```bash
occ --no-tailscale
```

**Work on a project with OpenCode:**
```bash
occ ~/Code/my-awesome-project
```

**Pass custom environment variables:**
```bash
export MY_API_KEY="secret123"
occ --env MY_API_KEY ~/Code/project
```

**Rebuild after modifying the Dockerfile:**
```bash
occ --rebuild --no-tailscale
```

**Check what containers are running:**
```bash
occ status
```

## Configuration

### Environment Variables

#### Runtime Selection

| Variable | Description |
|----------|-------------|
| `OCC_RUNTIME` | Force a specific container runtime (`docker` or `container`) |
| `OCC_DEBUG` | Set to `1` to print debug information including all env vars |

#### Tailscale

| Variable | Description |
|----------|-------------|
| `TS_AUTHKEY` | Tailscale auth key for automatic network connection |

### Environment Variable Allowlist

The following environment variables are automatically passed through to the container if set on the host:

```
TS_AUTHKEY          # Tailscale authentication
LANG                # Locale settings
LC_ALL
LC_CTYPE
EDITOR              # Preferred editor
TERM                # Terminal type

# API Keys
ANTHROPIC_API_KEY
OPENAI_API_KEY
OPENROUTER_API_KEY

# AWS Credentials
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN

# GitHub Tokens
GITHUB_TOKEN
GH_TOKEN
```

### Project `.env` File

If your project directory contains a `.env` file, it will be automatically parsed and the variables passed to the container.

```bash
# ~/Code/myproject/.env
DATABASE_URL=postgres://localhost/mydb
API_SECRET=mysecret
```

**Precedence order** (highest to lowest):
1. Implicit vars (`HOST_UID`, `HOST_GID`, `NO_TAILSCALE`)
2. Project `.env` file
3. `--env` flag values
4. Allowlist values from host environment

### Customizing the Dockerfile

The container image is built from `~/.config/occ/Dockerfile`. You can modify this file to:

- Add additional packages
- Install custom tools
- Change the base image
- Modify the entrypoint behavior

After making changes, rebuild with:
```bash
occ --rebuild
```

### Config Directory Structure

```
~/.config/occ/
├── Dockerfile      # Container image definition
└── .gitignore      # Ignores *.key, tailscale-*, .env
```

## Troubleshooting

### No container runtime found

**Error:** `Error: No container runtime found. Install Docker or the Apple 'container' CLI.`

**Solution:** Install Docker Desktop or ensure the Apple container CLI is available (macOS 26+). Alternatively, set `OCC_RUNTIME` to specify a runtime path.

### TS_AUTHKEY not set

**Error:** `Tailscale skipped (no TS_AUTHKEY set)`

**Solution:** Either:
1. Export your Tailscale auth key: `export TS_AUTHKEY="tskey-auth-xxxxx"`
2. Use `--no-tailscale` to skip Tailscale setup entirely

### OpenCode config directory not found

**Error:** `Error: OpenCode config directory not found: ~/.config/opencode`

**Solution:** Install and configure OpenCode first:
```bash
curl -fsSL https://opencode.ai/install | bash
```

### Project path doesn't exist

**Error:** `Error: Project path does not exist: /path/to/project`

**Solution:** Verify the path exists and is spelled correctly. Use absolute or relative paths.

### Project path is not a directory

**Error:** `Error: Project path is not a directory: /path/to/file`

**Solution:** Provide a directory path, not a file path.

### Image build fails

**Error:** `Error: Image build failed!`

**Solution:**
1. Check the build output for specific errors
2. Ensure you have internet connectivity (for package downloads)
3. Try rebuilding: `occ --rebuild`
4. Check available disk space

### Tailscale connection timeout

**Error:** `ERROR: Tailscale connection timeout after 30s`

**Solution:**
1. Verify your `TS_AUTHKEY` is valid and not expired
2. Check your Tailscale account status
3. Ensure no network/firewall is blocking Tailscale
4. Try generating a new auth key from the Tailscale admin console

### Malformed .env file

**Warning:** `Warning: Malformed line X in .env, skipping: ...`

**Solution:** Ensure your `.env` file follows the format:
```
KEY=value
# Comments start with #
```
No shell expansion, quotes, or multiline values are supported.

### Wrong file ownership in mounted directories

**Problem:** Files created in `/workspace` have wrong ownership on host.

**Solution:** This should be handled automatically via `HOST_UID`/`HOST_GID`. If issues persist:
1. Check that your user's UID/GID are being passed correctly (`OCC_DEBUG=1 occ ...`)
2. Ensure the entrypoint is running properly

## Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Host (macOS)                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  occ CLI                                             │   │
│  │  • Argument parsing                                  │   │
│  │  • Runtime detection (Docker / Apple container)     │   │
│  │  • Environment variable collection                  │   │
│  │  • Image build orchestration                        │   │
│  │  • Container launch                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Container (occ-workspace)                          │   │
│  │  ┌───────────────────────────────────────────────┐  │   │
│  │  │  /entrypoint.sh                               │  │   │
│  │  │  • User UID/GID mapping                       │  │   │
│  │  │  • Tailscale setup (optional)                 │  │   │
│  │  │  • Exec as user                               │  │   │
│  │  └───────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  │  Mounts:                                            │   │
│  │  • ~/.config/opencode → /home/user/.config/opencode │   │
│  │  • PROJECT_PATH → /workspace                        │   │
│  │                                                      │   │
│  │  Tools: opencode, git, nvim, tmux, node, python,   │   │
│  │         mise, uv, tailscale, ripgrep, fzf, jq, yq  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Location (source) | Location (installed) | Purpose |
|-----------|------------------|---------------------|---------|
| `Dockerfile` | `./Dockerfile` | `~/.config/occ/Dockerfile` | Wolfi-based image definition |
| `occ` | `./occ` | `~/.local/bin/occ` | Main CLI script |
| `install.sh` | `./install.sh` | N/A (run once) | One-time installer |

### Container Image

- **Base:** `cgr.dev/chainguard/wolfi-base:latest` (glibc-based minimal Linux)
- **Multi-arch:** Supports both `linux/arm64` and `linux/amd64`
- **Ephemeral:** Containers run with `--rm` flag; destroyed on exit

### Runtime Abstraction

`occ` supports both Docker and Apple's container CLI through runtime-agnostic helper functions:

| Operation | Apple `container` CLI | Docker |
|-----------|----------------------|--------|
| Build | `container build --tag NAME .` | `docker build -t NAME .` |
| Run | `container run --rm -it ...` | `docker run --rm -it ...` |
| Mount | `--mount type=bind,src=X,dst=Y` | `-v X:Y` |
| List | `container list` | `docker ps` |

For detailed architecture information, see `prd.md`.

## Security Considerations

- **Allowlist-only env passthrough:** Only explicitly allowed variables are passed to the container
- **Readonly config mount:** OpenCode config is mounted read-only
- **Ephemeral containers:** No persistent state; clean environment every run
- **No SSH/git config mount:** Minimizes host exposure (v1 limitation)
- **Host-side .env parsing:** `.env` files are parsed on the host; only key-value pairs are passed as flags

## License

MIT
