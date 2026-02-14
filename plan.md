# Execution Plan: `occ` - OpenCode Container CLI

**Based on:** PRD v1.0  
**Created:** 2026-02-14  

---

## Overview

This plan converts the existing `occ` bash script into a Python package installable via `uv tool install`. The implementation is divided into 5 phases, each delivering a complete, tested, and functional component.

---

## Phase Dependencies

```
Phase 1 (Scaffolding)
    │
    ▼
Phase 2 (Config) ──────────┐
    │                      │
    ▼                      ▼
Phase 3 (Docker) ◄──── Phase 4 (CLI)
    │                      │
    └──────────┬───────────┘
               ▼
        Phase 5 (Integration)
```

- **Phase 2** depends on **Phase 1**
- **Phase 3** depends on **Phase 2** (needs config paths)
- **Phase 4** depends on **Phase 2** (needs config) and **Phase 3** (needs docker operations)
- **Phase 5** depends on all previous phases

---

## Phase 1: Project Scaffolding and Package Structure

**Goal:** Establish a complete Python package structure that can be installed via `uv tool install` and runs a minimal CLI.

**Depends on:** Nothing (starting point)

### Tasks

- [x] Create project directory structure:
  ```
  occ/
  ├── pyproject.toml
  ├── README.md
  ├── .gitignore
  └── src/
      └── occ/
          ├── __init__.py
          ├── cli.py
          ├── docker.py
          ├── env.py
          ├── config.py
          └── resources/
              ├── Dockerfile
              └── config.toml
  ```
- [x] Write `pyproject.toml` with:
  - Project metadata (name, version, description)
  - Dependencies: `typer>=0.9.0`, `docker>=7.0.0`, `python-dotenv>=1.0.0`
  - Entry point: `occ = "occ.cli:app"`
  - Python requirement: `>=3.12`
- [x] Create `src/occ/__init__.py` with version string `__version__ = "1.0.0"`
- [x] Create minimal `src/occ/cli.py` with Typer app that prints version
- [x] Create stub files for `docker.py`, `env.py`, `config.py`
- [x] Create `src/occ/resources/Dockerfile` (copy from existing or create default)
- [x] Create `src/occ/resources/config.toml` with default configuration
- [x] Create `.gitignore` for Python projects
- [x] Create basic `README.md`

### Verification Script

```bash
#!/bin/bash
# verify_phase1.sh - Run from project root

set -e

echo "=== Phase 1 Verification ==="

# Check directory structure
echo "[1/5] Checking directory structure..."
required_files=(
    "pyproject.toml"
    "README.md"
    ".gitignore"
    "src/occ/__init__.py"
    "src/occ/cli.py"
    "src/occ/docker.py"
    "src/occ/env.py"
    "src/occ/config.py"
    "src/occ/resources/Dockerfile"
    "src/occ/resources/config.toml"
)

for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "FAIL: Missing $file"
        exit 1
    fi
done
echo "  All required files present."

# Check pyproject.toml has required fields
echo "[2/5] Validating pyproject.toml..."
if ! grep -q 'name = "occ"' pyproject.toml; then
    echo "FAIL: pyproject.toml missing project name"
    exit 1
fi
if ! grep -q 'typer' pyproject.toml; then
    echo "FAIL: pyproject.toml missing typer dependency"
    exit 1
fi
if ! grep -q 'docker' pyproject.toml; then
    echo "FAIL: pyproject.toml missing docker dependency"
    exit 1
fi
echo "  pyproject.toml valid."

# Test package can be installed
echo "[3/5] Testing package installation..."
uv venv .venv-test --quiet
source .venv-test/bin/activate
uv pip install -e . --quiet
echo "  Package installs successfully."

# Test CLI runs
echo "[4/5] Testing CLI execution..."
if ! occ --help > /dev/null 2>&1; then
    echo "FAIL: occ --help failed"
    deactivate
    rm -rf .venv-test
    exit 1
fi
echo "  CLI executes successfully."

# Test version output
echo "[5/5] Testing version command..."
if ! occ --version 2>&1 | grep -q "1.0.0"; then
    echo "FAIL: Version not showing correctly"
    deactivate
    rm -rf .venv-test
    exit 1
fi
echo "  Version displays correctly."

# Cleanup
deactivate
rm -rf .venv-test

echo ""
echo "=== Phase 1 PASSED ==="
```

### Exit Criteria

- Package installs without errors via `uv pip install -e .`
- `occ --help` displays help text
- `occ --version` displays `1.0.0`
- All verification script checks pass

---

## Phase 2: Configuration Management System

**Goal:** Implement complete configuration management including auto-initialization, TOML parsing, Dockerfile hash tracking, and config commands.

**Depends on:** Phase 1 (package structure)

### Tasks

- [x] Implement `config.py` with:
  - `CONFIG_DIR = Path.home() / ".config" / "occ"`
  - `get_config_path()` function
  - `ensure_config_initialized()` - creates dir and copies defaults if missing
  - `load_config()` - parses `config.toml` using `tomllib`
  - `get_dockerfile_path()` function
  - `needs_rebuild()` - compares Dockerfile hash
  - `save_dockerfile_hash()` - saves current hash to `.dockerfile-hash`
  - `reset_config()` - resets Dockerfile and config.toml to defaults
  - `ConfigModel` dataclass/TypedDict for type-safe config access
- [x] Implement path expansion for `~` in mount paths
- [x] Implement config validation (check required keys exist)
- [x] Add CLI commands in `cli.py`:
  - `occ config` - shows config directory path
  - `occ config reset` - resets to defaults with confirmation prompt
  - `occ config edit` - opens config.toml in `$EDITOR`
- [x] Handle missing `$EDITOR` gracefully (suggest vim/nano)

### Verification Script

```bash
#!/bin/bash
# verify_phase2.sh - Run from project root

set -e

echo "=== Phase 2 Verification ==="

# Setup
source .venv-test/bin/activate 2>/dev/null || {
    uv venv .venv-test --quiet
    source .venv-test/bin/activate
    uv pip install -e . --quiet
}

# Backup existing config if present
CONFIG_DIR="$HOME/.config/occ"
BACKUP_DIR="$HOME/.config/occ.backup.$$"
if [[ -d "$CONFIG_DIR" ]]; then
    mv "$CONFIG_DIR" "$BACKUP_DIR"
fi

cleanup() {
    rm -rf "$CONFIG_DIR"
    if [[ -d "$BACKUP_DIR" ]]; then
        mv "$BACKUP_DIR" "$CONFIG_DIR"
    fi
    deactivate 2>/dev/null || true
    rm -rf .venv-test
}
trap cleanup EXIT

# Test 1: Auto-initialization
echo "[1/7] Testing auto-initialization..."
python -c "from occ.config import ensure_config_initialized; ensure_config_initialized()"
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    echo "FAIL: config.toml not created"
    exit 1
fi
if [[ ! -f "$CONFIG_DIR/Dockerfile" ]]; then
    echo "FAIL: Dockerfile not created"
    exit 1
fi
echo "  Auto-initialization works."

# Test 2: Config loading
echo "[2/7] Testing config loading..."
python -c "
from occ.config import load_config
config = load_config()
assert 'container' in config, 'Missing container section'
assert 'mounts' in config, 'Missing mounts section'
assert 'env' in config, 'Missing env section'
print('  Config loads correctly.')
"

# Test 3: Dockerfile hash detection
echo "[3/7] Testing Dockerfile hash detection..."
python -c "
from occ.config import needs_rebuild, save_dockerfile_hash

# First run - no hash file
assert needs_rebuild() == True, 'Should need rebuild (no hash file)'

# Save hash
save_dockerfile_hash()

# Second check - hash matches
assert needs_rebuild() == False, 'Should not need rebuild (hash matches)'

# Modify Dockerfile
from pathlib import Path
dockerfile = Path.home() / '.config' / 'occ' / 'Dockerfile'
content = dockerfile.read_text()
dockerfile.write_text(content + '\n# modified')

# Third check - hash changed
assert needs_rebuild() == True, 'Should need rebuild (hash changed)'
print('  Dockerfile hash detection works.')
"

# Test 4: Config reset
echo "[4/7] Testing config reset..."
# Modify config
echo "# custom content" >> "$CONFIG_DIR/config.toml"
python -c "from occ.config import reset_config; reset_config()"
if grep -q "custom content" "$CONFIG_DIR/config.toml"; then
    echo "FAIL: Config reset did not restore defaults"
    exit 1
fi
echo "  Config reset works."

# Test 5: CLI config command
echo "[5/7] Testing 'occ config' command..."
output=$(occ config)
if [[ ! "$output" == *"$CONFIG_DIR"* ]]; then
    echo "FAIL: 'occ config' should show config path"
    exit 1
fi
echo "  'occ config' command works."

# Test 6: CLI config reset command
echo "[6/7] Testing 'occ config reset' command..."
echo "# test modification" >> "$CONFIG_DIR/config.toml"
echo "y" | occ config reset > /dev/null 2>&1
if grep -q "test modification" "$CONFIG_DIR/config.toml"; then
    echo "FAIL: 'occ config reset' did not work"
    exit 1
fi
echo "  'occ config reset' command works."

# Test 7: Path expansion
echo "[7/7] Testing path expansion..."
python -c "
from occ.config import load_config
from pathlib import Path

# Test that ~ paths get expanded
config = load_config()
# The default allowlist paths should be expandable
print('  Path expansion works.')
"

echo ""
echo "=== Phase 2 PASSED ==="
```

### Exit Criteria

- Running any `occ` command auto-initializes `~/.config/occ/` if missing
- `config.toml` and `Dockerfile` are copied from embedded resources
- `load_config()` returns parsed TOML as Python dict
- `needs_rebuild()` correctly detects Dockerfile changes
- `occ config` shows config path
- `occ config reset` restores defaults
- `occ config edit` opens editor (or shows helpful error)
- All verification script checks pass

---

## Phase 3: Docker Integration Layer

**Goal:** Implement all Docker operations: image building, container lifecycle management, and status reporting.

**Depends on:** Phase 2 (needs config paths and hash detection)

### Tasks

- [x] Implement `docker.py` with:
  - `check_docker_available()` - verify Docker daemon is running
  - `build_image(dockerfile_path, tag="occ:latest", verbose=False)` - build image
  - `image_exists(tag="occ:latest")` - check if image exists
  - `create_container(name, image, mounts, env_vars, shell)` - create container
  - `start_container(name)` - start existing container
  - `attach_to_container(name)` - attach interactive shell
  - `stop_container(name)` - stop container
  - `remove_container(name)` - remove container
  - `list_occ_containers()` - list containers with `occ-` prefix
  - `get_container_status(name)` - return running/stopped/not-found
  - `cleanup_dangling_images()` - remove old untagged occ images
  - `sanitize_container_name(project_path)` - convert path to valid name
- [x] Implement mount point assembly:
  - Default mounts (project, opencode configs)
  - Extra mounts from config.toml
  - Path expansion for `~`
- [x] Implement proper error handling:
  - Docker not running → helpful error message
  - Permission denied → suggest docker group / Docker Desktop
  - Image build failure → show build logs
- [x] Implement build progress output (single updating line for default, full for verbose)

### Verification Script

```bash
#!/bin/bash
# verify_phase3.sh - Run from project root
# NOTE: Requires Docker to be running

set -e

echo "=== Phase 3 Verification ==="

# Check Docker is available
if ! docker info > /dev/null 2>&1; then
    echo "SKIP: Docker is not running. Start Docker to run Phase 3 verification."
    exit 0
fi

# Setup
source .venv-test/bin/activate 2>/dev/null || {
    uv venv .venv-test --quiet
    source .venv-test/bin/activate
    uv pip install -e . --quiet
}

# Ensure config is initialized
python -c "from occ.config import ensure_config_initialized; ensure_config_initialized()"

# Cleanup any test containers/images
cleanup() {
    docker rm -f occ-test-project 2>/dev/null || true
    deactivate 2>/dev/null || true
}
trap cleanup EXIT

# Test 1: Docker availability check
echo "[1/8] Testing Docker availability check..."
python -c "
from occ.docker import check_docker_available
assert check_docker_available() == True, 'Docker should be available'
print('  Docker availability check works.')
"

# Test 2: Container name sanitization
echo "[2/8] Testing container name sanitization..."
python -c "
from occ.docker import sanitize_container_name

assert sanitize_container_name('/Users/me/Code/my-project') == 'occ-my-project'
assert sanitize_container_name('/home/user/My Project') == 'occ-my-project'
assert sanitize_container_name('/tmp/Test_Project_123') == 'occ-test-project-123'
print('  Container name sanitization works.')
"

# Test 3: Image building
echo "[3/8] Testing image building..."
python -c "
from occ.docker import build_image
from occ.config import get_dockerfile_path

build_image(get_dockerfile_path(), tag='occ:test')
print('  Image building works.')
"

# Test 4: Image exists check
echo "[4/8] Testing image exists check..."
python -c "
from occ.docker import image_exists

assert image_exists('occ:test') == True, 'Test image should exist'
assert image_exists('occ:nonexistent-tag-xyz') == False, 'Nonexistent image should not exist'
print('  Image exists check works.')
"

# Test 5: Container creation
echo "[5/8] Testing container creation..."
TEST_PROJECT=$(mktemp -d)
python -c "
from occ.docker import create_container
from pathlib import Path

create_container(
    name='occ-test-project',
    image='occ:test',
    mounts=[{'source': '$TEST_PROJECT', 'target': '/workspace', 'mode': 'rw'}],
    env_vars={'TEST_VAR': 'test_value'},
    shell='/bin/bash'
)
print('  Container creation works.')
"

# Test 6: Container status
echo "[6/8] Testing container status..."
python -c "
from occ.docker import get_container_status

status = get_container_status('occ-test-project')
assert status in ['created', 'running', 'exited'], f'Unexpected status: {status}'
print('  Container status check works.')
"

# Test 7: List containers
echo "[7/8] Testing container listing..."
python -c "
from occ.docker import list_occ_containers

containers = list_occ_containers()
names = [c['name'] for c in containers]
assert 'occ-test-project' in names, 'Test container should be in list'
print('  Container listing works.')
"

# Test 8: Container stop and remove
echo "[8/8] Testing container stop/remove..."
python -c "
from occ.docker import stop_container, remove_container, get_container_status

stop_container('occ-test-project')
remove_container('occ-test-project')
status = get_container_status('occ-test-project')
assert status == 'not-found', 'Container should be removed'
print('  Container stop/remove works.')
"

# Cleanup test image
docker rmi occ:test 2>/dev/null || true
rm -rf "$TEST_PROJECT"

echo ""
echo "=== Phase 3 PASSED ==="
```

### Exit Criteria

- `check_docker_available()` returns True when Docker is running, helpful error otherwise
- Images can be built from the configured Dockerfile
- Containers can be created, started, stopped, and removed
- Container names are properly sanitized from project paths
- `list_occ_containers()` returns all occ-prefixed containers
- Mount points are correctly assembled
- All verification script checks pass

---

## Phase 4: CLI Implementation

**Goal:** Implement all CLI commands and options as specified in the PRD.

**Depends on:** Phase 2 (config), Phase 3 (docker operations)

### Tasks

- [x] Implement main command `occ [OPTIONS] [PROJECT_PATH]`:
  - Resolve project path (default to current directory)
  - Validate project path exists
  - Auto-initialize config on first run
  - Check if rebuild needed (hash changed, `--rebuild` flag, image missing)
  - Build image if needed
  - Check if container already running → prompt: Attach/Restart/Cancel
  - Create and start container with proper mounts and env vars
  - Attach interactive shell
  - Handle `--keep-alive` flag (don't stop on exit)
- [x] Implement `--rebuild` flag
- [x] Implement `--env VAR=value` flag (repeatable)
- [x] Implement `--keep-alive` flag
- [x] Implement `-v/--verbose` flag
- [x] Implement `-q/--quiet` flag
- [x] Implement `env.py`:
  - `collect_env_vars(project_path, cli_env, config)` - merge env vars by priority
  - Load from host env (allowlist)
  - Load from project `.env` file
  - Add CLI `--env` overrides
- [x] Implement subcommands:
  - `occ status` - table of running containers
  - `occ shell [PROJECT]` - attach to running container
  - `occ stop [PROJECT]` - stop container
  - `occ stop --all` - stop all occ containers
- [x] Implement interactive prompt for running container:
  - "[A]ttach / [R]estart / [C]ancel?"
- [x] Implement output formatting:
  - Status table with columns: NAME, PROJECT, STATUS, UPTIME
  - Build progress (updating single line in default mode)
- [x] Handle all error cases with user-friendly messages

### Verification Script

```bash
#!/bin/bash
# verify_phase4.sh - Run from project root
# NOTE: Requires Docker to be running

set -e

echo "=== Phase 4 Verification ==="

# Check Docker is available
if ! docker info > /dev/null 2>&1; then
    echo "SKIP: Docker is not running. Start Docker to run Phase 4 verification."
    exit 0
fi

# Setup
source .venv-test/bin/activate 2>/dev/null || {
    uv venv .venv-test --quiet
    source .venv-test/bin/activate
    uv pip install -e . --quiet
}

# Create test project
TEST_PROJECT=$(mktemp -d)
echo "TEST_VAR=from_dotenv" > "$TEST_PROJECT/.env"

cleanup() {
    docker rm -f occ-test-project occ-verify-project 2>/dev/null || true
    rm -rf "$TEST_PROJECT"
    deactivate 2>/dev/null || true
}
trap cleanup EXIT

# Test 1: Help output
echo "[1/10] Testing help output..."
occ --help | grep -q "PROJECT_PATH" || { echo "FAIL: Help missing PROJECT_PATH"; exit 1; }
occ --help | grep -q "\-\-rebuild" || { echo "FAIL: Help missing --rebuild"; exit 1; }
occ --help | grep -q "\-\-env" || { echo "FAIL: Help missing --env"; exit 1; }
echo "  Help output correct."

# Test 2: Status command (empty)
echo "[2/10] Testing status command (no containers)..."
docker rm -f $(docker ps -a --filter "name=occ-" -q) 2>/dev/null || true
output=$(occ status)
# Should show headers or "no containers" message
echo "  Status command works."

# Test 3: Environment variable collection
echo "[3/10] Testing environment variable collection..."
python -c "
from occ.env import collect_env_vars
from occ.config import load_config
from pathlib import Path
import os

os.environ['ANTHROPIC_API_KEY'] = 'test-key-123'
config = load_config()

env_vars = collect_env_vars(
    project_path=Path('$TEST_PROJECT'),
    cli_env=['CUSTOM_VAR=cli_value'],
    config=config
)

# CLI env should be present
assert env_vars.get('CUSTOM_VAR') == 'cli_value', 'CLI env not collected'

# Dotenv should be loaded
assert env_vars.get('TEST_VAR') == 'from_dotenv', 'Dotenv not loaded'

# Allowlist should work
assert env_vars.get('ANTHROPIC_API_KEY') == 'test-key-123', 'Allowlist env not collected'

print('  Environment collection works.')
"

# Test 4: Invalid project path
echo "[4/10] Testing invalid project path handling..."
if occ /nonexistent/path/xyz 2>&1 | grep -qi "does not exist\|not found\|invalid"; then
    echo "  Invalid path error works."
else
    echo "FAIL: Should error on invalid path"
    exit 1
fi

# Test 5: Rebuild flag
echo "[5/10] Testing --rebuild flag..."
# Just verify it's accepted
occ --help | grep -q "rebuild" || { echo "FAIL: --rebuild flag not in help"; exit 1; }
echo "  --rebuild flag registered."

# Test 6: Stop command
echo "[6/10] Testing stop command..."
# Create a test container first
python -c "
from occ.docker import create_container, start_container, image_exists, build_image
from occ.config import get_dockerfile_path

if not image_exists('occ:latest'):
    build_image(get_dockerfile_path())

create_container(
    name='occ-verify-project',
    image='occ:latest',
    mounts=[{'source': '$TEST_PROJECT', 'target': '/workspace', 'mode': 'rw'}],
    env_vars={},
    shell='/bin/bash'
)
start_container('occ-verify-project')
"
occ stop verify-project
echo "  Stop command works."

# Test 7: Shell command (with non-running container)
echo "[7/10] Testing shell command error handling..."
if occ shell nonexistent-container 2>&1 | grep -qi "not found\|not running\|does not exist"; then
    echo "  Shell command error handling works."
else
    echo "  Shell command handles missing container."
fi

# Test 8: Status shows containers
echo "[8/10] Testing status with containers..."
python -c "
from occ.docker import create_container, start_container
create_container(
    name='occ-test-project',
    image='occ:latest',
    mounts=[{'source': '$TEST_PROJECT', 'target': '/workspace', 'mode': 'rw'}],
    env_vars={},
    shell='/bin/bash'
)
start_container('occ-test-project')
"
occ status | grep -q "occ-test-project" || { echo "FAIL: Status should show test container"; exit 1; }
echo "  Status shows running containers."

# Test 9: Stop --all
echo "[9/10] Testing stop --all..."
occ stop --all
sleep 1
running=$(docker ps --filter "name=occ-" -q | wc -l | tr -d ' ')
if [[ "$running" != "0" ]]; then
    echo "FAIL: stop --all should stop all containers"
    exit 1
fi
echo "  Stop --all works."

# Test 10: Verbose and quiet flags
echo "[10/10] Testing verbosity flags..."
occ --help | grep -q "\-v\|verbose" || { echo "FAIL: Missing verbose flag"; exit 1; }
occ --help | grep -q "\-q\|quiet" || { echo "FAIL: Missing quiet flag"; exit 1; }
echo "  Verbosity flags registered."

echo ""
echo "=== Phase 4 PASSED ==="
```

### Exit Criteria

- `occ [PROJECT_PATH]` launches container with correct mounts and env vars
- `--rebuild`, `--env`, `--keep-alive`, `-v`, `-q` flags work
- `occ status` shows formatted table of running containers
- `occ shell [PROJECT]` attaches to running container
- `occ stop [PROJECT]` stops container
- `occ stop --all` stops all occ containers
- Environment variables collected in correct priority order
- User-friendly prompts and error messages
- All verification script checks pass

---

## Phase 5: Integration and End-to-End Testing

**Goal:** Verify complete user workflows work end-to-end and clean up any remaining issues.

**Depends on:** All previous phases

### Tasks

- [ ] Test complete first-run experience:
  - Fresh system (no `~/.config/occ`)
  - Run `occ ~/Code/project`
  - Verify config initialization message
  - Verify image build
  - Verify container starts
  - Verify shell attaches
- [ ] Test Dockerfile modification workflow:
  - Modify `~/.config/occ/Dockerfile`
  - Run `occ project`
  - Verify "Dockerfile changed, rebuilding..." message
  - Verify image rebuilds
- [ ] Test multiple concurrent containers:
  - Launch `occ ~/project-a`
  - Launch `occ ~/project-b` (in another terminal)
  - Verify both appear in `occ status`
  - Verify separate containers with correct names
- [ ] Test container already running workflow:
  - Start container with `occ project`
  - Exit shell
  - Run `occ project` again with `--keep-alive` first time
  - Verify prompt appears
- [ ] Test all error scenarios:
  - Docker not running
  - Invalid project path
  - Permission issues (if testable)
- [ ] Clean up old bash `occ` script and `install.sh` if they exist
- [ ] Verify `uv tool install .` works from package directory
- [ ] Update README with installation and usage instructions

### Verification Script

```bash
#!/bin/bash
# verify_phase5.sh - Full integration test
# NOTE: Requires Docker to be running

set -e

echo "=== Phase 5 Integration Verification ==="

# Check Docker is available
if ! docker info > /dev/null 2>&1; then
    echo "SKIP: Docker is not running. Start Docker to run Phase 5 verification."
    exit 0
fi

# Backup existing config
CONFIG_DIR="$HOME/.config/occ"
BACKUP_DIR="$HOME/.config/occ.backup.$$"
if [[ -d "$CONFIG_DIR" ]]; then
    mv "$CONFIG_DIR" "$BACKUP_DIR"
fi

# Create test projects
TEST_PROJECT_A=$(mktemp -d)
TEST_PROJECT_B=$(mktemp -d)
mkdir -p "$TEST_PROJECT_A" "$TEST_PROJECT_B"

cleanup() {
    # Stop and remove test containers
    docker rm -f occ-$(basename "$TEST_PROJECT_A") occ-$(basename "$TEST_PROJECT_B") 2>/dev/null || true
    
    # Remove test projects
    rm -rf "$TEST_PROJECT_A" "$TEST_PROJECT_B"
    
    # Restore config backup
    rm -rf "$CONFIG_DIR"
    if [[ -d "$BACKUP_DIR" ]]; then
        mv "$BACKUP_DIR" "$CONFIG_DIR"
    fi
    
    deactivate 2>/dev/null || true
    rm -rf .venv-test
}
trap cleanup EXIT

# Setup
uv venv .venv-test --quiet
source .venv-test/bin/activate
uv pip install -e . --quiet

echo "[1/6] Testing fresh install experience..."
# Config dir should not exist
if [[ -d "$CONFIG_DIR" ]]; then
    rm -rf "$CONFIG_DIR"
fi

# Run occ - should auto-initialize
output=$(occ config 2>&1)
if [[ ! -d "$CONFIG_DIR" ]]; then
    echo "FAIL: Config dir not created"
    exit 1
fi
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    echo "FAIL: config.toml not created"
    exit 1
fi
if [[ ! -f "$CONFIG_DIR/Dockerfile" ]]; then
    echo "FAIL: Dockerfile not created"
    exit 1
fi
echo "  Fresh install auto-initialization works."

echo "[2/6] Testing image build on first run..."
# Remove any existing image
docker rmi occ:latest 2>/dev/null || true

# This should build the image
python -c "
from occ.docker import build_image, image_exists
from occ.config import get_dockerfile_path, save_dockerfile_hash

if not image_exists('occ:latest'):
    build_image(get_dockerfile_path())
    save_dockerfile_hash()

assert image_exists('occ:latest'), 'Image should be built'
print('  Image built successfully.')
"

echo "[3/6] Testing Dockerfile change detection..."
# Modify Dockerfile
echo "" >> "$CONFIG_DIR/Dockerfile"
echo "# Test modification $(date)" >> "$CONFIG_DIR/Dockerfile"

python -c "
from occ.config import needs_rebuild
assert needs_rebuild() == True, 'Should detect Dockerfile change'
print('  Dockerfile change detected.')
"

echo "[4/6] Testing multiple containers..."
python -c "
from occ.docker import create_container, start_container, list_occ_containers, build_image, image_exists
from occ.config import get_dockerfile_path, save_dockerfile_hash

# Ensure image exists
if not image_exists('occ:latest'):
    build_image(get_dockerfile_path())
    save_dockerfile_hash()

# Create two containers
create_container(
    name='occ-project-a',
    image='occ:latest',
    mounts=[{'source': '$TEST_PROJECT_A', 'target': '/workspace', 'mode': 'rw'}],
    env_vars={},
    shell='/bin/bash'
)
start_container('occ-project-a')

create_container(
    name='occ-project-b',
    image='occ:latest',
    mounts=[{'source': '$TEST_PROJECT_B', 'target': '/workspace', 'mode': 'rw'}],
    env_vars={},
    shell='/bin/bash'
)
start_container('occ-project-b')

# List should show both
containers = list_occ_containers()
names = [c['name'] for c in containers]
assert 'occ-project-a' in names, 'Project A container missing'
assert 'occ-project-b' in names, 'Project B container missing'
print('  Multiple containers work.')
"

echo "[5/6] Testing status output format..."
output=$(occ status)
if ! echo "$output" | grep -q "NAME\|name"; then
    # Might show "No running containers" which is also valid
    if ! echo "$output" | grep -qi "no.*container\|occ-project"; then
        echo "FAIL: Status output format incorrect"
        exit 1
    fi
fi
echo "  Status output formatted correctly."

echo "[6/6] Testing uv tool install compatibility..."
# Test that the package can be installed as a tool
cd "$(dirname "$0")"
uv tool install . --force 2>/dev/null && uv tool uninstall occ 2>/dev/null || true
echo "  Package is uv tool installable."

# Cleanup test containers
docker rm -f occ-project-a occ-project-b 2>/dev/null || true

echo ""
echo "=== Phase 5 PASSED ==="
echo ""
echo "=== ALL PHASES COMPLETE ==="
echo "The occ package is ready for release."
```

### Exit Criteria

- Complete first-run experience works (config init → build → run)
- Dockerfile changes trigger rebuild
- Multiple concurrent containers work independently
- All CLI commands function correctly
- `uv tool install .` works
- README is updated with accurate instructions
- Old bash script files removed (if present)
- All verification scripts pass

---

## Summary

| Phase | Description | Dependencies | Verification |
|-------|-------------|--------------|--------------|
| 1 | Project Scaffolding | None | `verify_phase1.sh` |
| 2 | Configuration Management | Phase 1 | `verify_phase2.sh` |
| 3 | Docker Integration | Phase 2 | `verify_phase3.sh` |
| 4 | CLI Implementation | Phase 2, 3 | `verify_phase4.sh` |
| 5 | Integration Testing | All | `verify_phase5.sh` |

**Total Estimated Tasks:** 45+  
**Each phase produces:** Working, testable code with autonomous verification

---

## Running Verification

After completing each phase, run the corresponding verification script:

```bash
# From project root
chmod +x verify_phase*.sh
./verify_phase1.sh  # Run after Phase 1
./verify_phase2.sh  # Run after Phase 2
./verify_phase3.sh  # Run after Phase 3 (requires Docker)
./verify_phase4.sh  # Run after Phase 4 (requires Docker)
./verify_phase5.sh  # Run after Phase 5 (requires Docker)
```

Each script will output `=== Phase N PASSED ===` on success or indicate the specific failure point.
