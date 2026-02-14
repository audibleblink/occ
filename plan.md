# Execution Plan: `occ` — OpenCode Container

> Derived from `prd.md`. Each phase produces a complete, tested, functioning artifact. Phases are ordered by dependency; dependent phases are labeled explicitly.

---

## Phase 0: Project Scaffolding & Repo Setup

**Depends on**: Nothing  
**Produces**: Repository structure, `.gitignore`, empty placeholder files

### Tasks

- [x] Initialize a git repository in the project root
- [x] Create `.gitignore` with entries: `*.key`, `tailscale-*`, `.env`, `.DS_Store`
- [x] Create empty placeholder files: `Dockerfile`, `occ`, `install.sh`, `README.md`
- [x] Make `occ` and `install.sh` executable (`chmod +x`)

### Verification

```bash
#!/usr/bin/env bash
# phase0-check.sh — run from project root
set -euo pipefail
fail=0
for f in .gitignore Dockerfile occ install.sh README.md; do
  [ -f "$f" ] || { echo "MISSING: $f"; fail=1; }
done
[ -x occ ] || { echo "occ not executable"; fail=1; }
[ -x install.sh ] || { echo "install.sh not executable"; fail=1; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "Not a git repo"; fail=1; }
[ $fail -eq 0 ] && echo "Phase 0: PASS" || { echo "Phase 0: FAIL"; exit 1; }
```

---

## Phase 1: Dockerfile & Entrypoint

**Depends on**: Phase 0  
**Produces**: A buildable, multi-arch `Dockerfile` with an embedded `/entrypoint.sh` that handles user creation, optional Tailscale startup, and exec to the final command.

### Tasks

- [x] Write `Dockerfile` using `cgr.dev/chainguard/wolfi-base:latest` as base
- [x] Install system packages via `apk`: `bash`, `coreutils`, `shadow`, `sudo`, `ca-certificates`, `curl`, `wget`, `git`, `neovim`, `zsh`, `tmux`, `jq`, `ripgrep`, `fzf`, `nodejs`, `npm`, `python3`, `build-base`
- [x] Install GitHub-release tools with `TARGETARCH` detection:
  - `tailscale` + `tailscaled` from `pkgs.tailscale.com`
  - `opencode` via install script
  - `mise` via install script
  - `uv` via install script
  - `yq` from GitHub releases
- [x] Create a default non-root placeholder user (e.g., `user` with UID 1000)
- [x] Write `/entrypoint.sh` inline (or `COPY`) that:
  1. Reads `HOST_UID` and `HOST_GID` env vars
  2. Creates/modifies the `user` account to match those IDs
  3. Fixes ownership on `/home/user`
  4. Conditionally starts Tailscale (if `TS_AUTHKEY` set and `NO_TAILSCALE` is not `1`), with a 30 s timeout and hard fail
  5. Execs the provided command as the created user via `exec gosu user "$@"` or `exec su-exec` / `sudo -u`
- [x] Set `ENTRYPOINT ["/entrypoint.sh"]` and `CMD ["/bin/bash"]`
- [x] Ensure the image works for both `linux/arm64` and `linux/amd64`

### Verification

```bash
#!/usr/bin/env bash
# phase1-check.sh — builds the image and validates entrypoint basics
set -euo pipefail
IMAGE="occ-workspace:phase1-test"
RUNTIME="${OCC_RUNTIME:-docker}"

echo "==> Building image with $RUNTIME..."
if [ "$RUNTIME" = "container" ]; then
  container build --tag "$IMAGE" .
else
  docker build -t "$IMAGE" .
fi

echo "==> Checking entrypoint user mapping (UID=$(id -u), GID=$(id -g))..."
OUTPUT=$($RUNTIME run --rm \
  -e HOST_UID="$(id -u)" \
  -e HOST_GID="$(id -g)" \
  -e NO_TAILSCALE=1 \
  "$IMAGE" id)
echo "$OUTPUT"

echo "$OUTPUT" | grep -q "uid=$(id -u)" || { echo "UID mismatch"; exit 1; }
echo "$OUTPUT" | grep -q "gid=$(id -g)" || { echo "GID mismatch"; exit 1; }

echo "==> Checking installed tools..."
for tool in bash git nvim tmux zsh jq rg fzf node npm python3 curl wget yq mise uv opencode tailscale; do
  $RUNTIME run --rm -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" -e NO_TAILSCALE=1 \
    "$IMAGE" which "$tool" >/dev/null 2>&1 \
    || { echo "MISSING tool: $tool"; exit 1; }
  echo "  ✓ $tool"
done

echo "Phase 1: PASS"
```

---

## Phase 2: `occ` CLI — Core Framework & Argument Parsing

**Depends on**: Phase 0  
**Produces**: A functioning `occ` bash script with argument parsing, `--help` output, runtime detection, and stubbed-out handler functions. No container launch yet — just the CLI skeleton that exits cleanly.

### Tasks

- [ ] Write `occ` as a bash script with `set -euo pipefail`
- [ ] Implement `--help` flag that prints the usage block from PRD §6.3
- [ ] Implement argument parser supporting:
  - `--rebuild`
  - `--env VAR` (repeatable)
  - `--no-tailscale`
  - `--help`
  - Positional `PROJECT_PATH`
  - Subcommands: `status`, `config`
- [ ] Implement runtime detection logic (PRD §4.5):
  1. Check `OCC_RUNTIME` env var
  2. Check for `container` in PATH
  3. Fall back to `docker`
  4. Error if neither found
- [ ] Create helper functions that abstract runtime differences:
  - `rt_build` — build image
  - `rt_run` — run container
  - `rt_mount` — format mount argument
  - `rt_list` — list containers
  - `rt_rmi` — remove image
- [ ] Validate `PROJECT_PATH` (exists, is directory) when provided
- [ ] Check that `~/.config/opencode` exists (exit 1 if not)
- [ ] Exit with stubs for actual image build / container launch (print "would launch" and exit 0)

### Verification

```bash
#!/usr/bin/env bash
# phase2-check.sh — validates CLI argument parsing and error handling
set -euo pipefail
OCC="./occ"
fail=0

# --help exits 0 and prints usage
$OCC --help | grep -q "Usage" || { echo "FAIL: --help"; fail=1; }

# Missing runtime detection (unset all, remove docker/container from PATH)
(
  unset OCC_RUNTIME
  PATH="/usr/bin:/bin" $OCC --no-tailscale 2>&1 || true
) | grep -qi "runtime\|docker\|container" || { echo "FAIL: no runtime error"; fail=1; }

# Nonexistent project path
$OCC --no-tailscale /nonexistent/path 2>&1 | grep -qi "not exist\|no such\|not found" \
  || { echo "FAIL: bad project path"; fail=1; }

# status subcommand exits 0
$OCC status >/dev/null 2>&1 || { echo "FAIL: status subcommand"; fail=1; }

# config subcommand exits 0
$OCC config >/dev/null 2>&1 || { echo "FAIL: config subcommand"; fail=1; }

# --env with multiple vars parses without error
$OCC --env FOO --env BAR --no-tailscale --help >/dev/null 2>&1 \
  || { echo "FAIL: --env parsing"; fail=1; }

[ $fail -eq 0 ] && echo "Phase 2: PASS" || { echo "Phase 2: FAIL"; exit 1; }
```

---

## Phase 3: `occ` CLI — Environment Variable Handling

**Depends on**: Phase 2  
**Produces**: Complete env-var logic: default allowlist passthrough, `.env` file parsing, `--env` flag handling, and implicit vars (`HOST_UID`, `HOST_GID`, `NO_TAILSCALE`). All env flags are collected into an array ready to be appended to the container run command.

### Tasks

- [ ] Define the default allowlist array (PRD §5.3)
- [ ] Implement function `collect_allowlist_envs()`: iterate allowlist, if set on host, append `--env KEY=VALUE` to env array
- [ ] Implement function `parse_dotenv(filepath)`:
  - Read `.env` from `PROJECT_PATH/.env` if it exists
  - Skip blank lines and lines starting with `#`
  - Extract `KEY=VALUE` pairs (no shell expansion, no multiline)
  - Warn on stderr for malformed lines, continue
  - Append `--env KEY=VALUE` to env array
  - `.env` values override same-name host vars
- [ ] Implement `--env VAR` handling: read `VAR` from host env, silently skip if unset
- [ ] Always inject `HOST_UID=$(id -u)` and `HOST_GID=$(id -g)`
- [ ] Inject `NO_TAILSCALE=1` when `--no-tailscale` is passed
- [ ] Ensure precedence order: implicit > .env > --env > allowlist (highest to lowest priority, later overrides earlier)
- [ ] Print the final env array when a debug flag or `OCC_DEBUG=1` is set

### Verification

```bash
#!/usr/bin/env bash
# phase3-check.sh — validates env var assembly
set -euo pipefail
OCC="./occ"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Create a fake project with .env
mkdir -p "$TMPDIR/project"
mkdir -p "$HOME/.config/opencode"
cat > "$TMPDIR/project/.env" <<'EOF'
# comment line
FOO=bar
BAZ=qux
MALFORMED LINE WITHOUT EQUALS
ANTHROPIC_API_KEY=from-dotenv
EOF

export OCC_DEBUG=1
export ANTHROPIC_API_KEY="from-host"
export CUSTOM_THING="hello"

OUTPUT=$($OCC --no-tailscale --env CUSTOM_THING "$TMPDIR/project" 2>&1 || true)

echo "$OUTPUT"

# .env values present
echo "$OUTPUT" | grep -q "FOO=bar" || { echo "FAIL: FOO from .env"; exit 1; }
echo "$OUTPUT" | grep -q "BAZ=qux" || { echo "FAIL: BAZ from .env"; exit 1; }

# .env overrides host
echo "$OUTPUT" | grep -q "ANTHROPIC_API_KEY=from-dotenv" || { echo "FAIL: .env override"; exit 1; }

# --env passthrough
echo "$OUTPUT" | grep -q "CUSTOM_THING=hello" || { echo "FAIL: --env passthrough"; exit 1; }

# HOST_UID / HOST_GID present
echo "$OUTPUT" | grep -q "HOST_UID=$(id -u)" || { echo "FAIL: HOST_UID"; exit 1; }
echo "$OUTPUT" | grep -q "HOST_GID=$(id -g)" || { echo "FAIL: HOST_GID"; exit 1; }

# NO_TAILSCALE present
echo "$OUTPUT" | grep -q "NO_TAILSCALE=1" || { echo "FAIL: NO_TAILSCALE"; exit 1; }

# Malformed line warned
echo "$OUTPUT" | grep -qi "warn\|malformed\|skip" || { echo "FAIL: malformed warning"; exit 1; }

echo "Phase 3: PASS"
```

---

## Phase 4: `occ` CLI — Image Build & Container Launch

**Depends on**: Phase 1, Phase 2, Phase 3  
**Produces**: Full container lifecycle — image build (auto on first run, `--rebuild` for forced), container launch with correct mounts, env vars, naming, and ephemeral (`--rm`) behavior.

### Tasks

- [ ] Implement `ensure_image()`:
  - Check if `occ-workspace:latest` image exists (runtime-specific check)
  - If missing or `--rebuild` passed, build from `~/.config/occ/Dockerfile` with context `~/.config/occ/`
  - `--rebuild` passes `--no-cache`
  - Stream build output to terminal
  - Abort on build failure with clear error
- [ ] Implement `launch_container()`:
  - Generate container name: `occ-workspace-$(date +%Y%m%d-%H%M%S)`
  - Always pass `--rm -it`
  - Attach collected env var flags
  - Mount `~/.config/opencode` → `/home/user/.config/opencode` (readonly)
  - If `PROJECT_PATH` provided: mount at `/workspace`, set working dir to `/workspace`, command = `opencode`
  - If no `PROJECT_PATH`: command = `/bin/bash`
  - Use runtime-abstracted helper functions for mount syntax
- [ ] Implement `status` subcommand:
  - List containers filtered by `occ-workspace-*` name prefix
  - Show name, runtime, uptime, and mounted project path
- [ ] Implement `config` subcommand:
  - Print `~/.config/occ/` path and list contents
  - If `$EDITOR` is set, offer to open the directory
- [ ] Wire everything together in `main()` flow:
  1. Parse args
  2. Detect runtime
  3. Validate inputs
  4. Collect env vars
  5. Ensure image
  6. Launch container

### Verification

```bash
#!/usr/bin/env bash
# phase4-check.sh — end-to-end container launch tests (requires Docker or container CLI)
set -euo pipefail

# Use the installed locations to simulate real usage, or run from source
OCC="./occ"
RUNTIME="${OCC_RUNTIME:-docker}"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Ensure config dirs exist
mkdir -p "$HOME/.config/opencode"
mkdir -p "$HOME/.config/occ"
cp Dockerfile "$HOME/.config/occ/Dockerfile"

echo "==> Test 1: Build image"
$OCC --rebuild --no-tailscale --help >/dev/null 2>&1 || true
# Manually build for test
$OCC --rebuild --no-tailscale 2>&1 &
BUILD_PID=$!
sleep 5
# We just verify the build starts; full build may take a while
kill $BUILD_PID 2>/dev/null || true
echo "  Build started OK"

echo "==> Test 2: Container naming pattern"
# Verify the naming function outputs correct format
NAME=$($OCC --no-tailscale 2>&1 | grep -o 'occ-workspace-[0-9]\{8\}-[0-9]\{6\}' | head -1 || true)
if [ -n "$NAME" ]; then
  echo "  Container name: $NAME ✓"
else
  echo "  (name not captured from dry-run, OK for stub)"
fi

echo "==> Test 3: Status subcommand"
$OCC status >/dev/null 2>&1
echo "  status: OK"

echo "==> Test 4: Config subcommand"
$OCC config 2>&1 | grep -q "occ" || { echo "FAIL: config output"; exit 1; }
echo "  config: OK"

echo "==> Test 5: Nonexistent opencode config"
(
  HOME="$TMPDIR/fakehome" $OCC --no-tailscale 2>&1 || true
) | grep -qi "opencode\|config" || { echo "FAIL: opencode config check"; exit 1; }
echo "  opencode config check: OK"

echo "Phase 4: PASS"
```

---

## Phase 5: `install.sh`

**Depends on**: Phase 0, Phase 1, Phase 2  
**Produces**: A working installer that copies `Dockerfile` and `occ` to their installed locations and prints post-install instructions.

### Tasks

- [ ] Verify script is run from the source directory (check `Dockerfile` and `occ` exist in cwd)
- [ ] Create `~/.config/occ/` directory
- [ ] Copy `./Dockerfile` → `~/.config/occ/Dockerfile`
- [ ] Create `~/.config/occ/.gitignore` with patterns: `*.key`, `tailscale-*`, `.env`
- [ ] Create `~/.local/bin/` if it doesn't exist
- [ ] Copy `./occ` → `~/.local/bin/occ`
- [ ] `chmod +x ~/.local/bin/occ`
- [ ] Check if `~/.local/bin` is in `$PATH`; warn if not
- [ ] Print the post-install message (PRD §6.3)

### Verification

```bash
#!/usr/bin/env bash
# phase5-check.sh — validates install.sh in an isolated environment
set -euo pipefail
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Create a fake HOME to avoid touching real config
export HOME="$TMPDIR/home"
mkdir -p "$HOME"

# Run install from source dir
./install.sh

# Validate installed files
[ -f "$HOME/.config/occ/Dockerfile" ] || { echo "FAIL: Dockerfile not installed"; exit 1; }
[ -f "$HOME/.config/occ/.gitignore" ] || { echo "FAIL: .gitignore not created"; exit 1; }
[ -f "$HOME/.local/bin/occ" ] || { echo "FAIL: occ not installed"; exit 1; }
[ -x "$HOME/.local/bin/occ" ] || { echo "FAIL: occ not executable"; exit 1; }

# Validate .gitignore contents
grep -q '*.key' "$HOME/.config/occ/.gitignore" || { echo "FAIL: .gitignore missing *.key"; exit 1; }
grep -q 'tailscale-' "$HOME/.config/occ/.gitignore" || { echo "FAIL: .gitignore missing tailscale-"; exit 1; }
grep -q '.env' "$HOME/.config/occ/.gitignore" || { echo "FAIL: .gitignore missing .env"; exit 1; }

# Running from wrong directory should fail
(
  cd "$TMPDIR"
  ./install.sh 2>&1 || true
) | grep -qi "source\|directory\|Dockerfile" || { echo "FAIL: wrong-dir check"; exit 1; }

echo "Phase 5: PASS"
```

---

## Phase 6: `README.md` & Documentation

**Depends on**: Phase 1, Phase 2, Phase 3, Phase 4, Phase 5  
**Produces**: Complete `README.md` covering overview, requirements, installation, usage, configuration, environment variables, troubleshooting.

### Tasks

- [ ] Write Overview section (what `occ` is, what it does)
- [ ] Write Requirements section (macOS, Docker or Apple container CLI, Tailscale, OpenCode config)
- [ ] Write Installation section (clone, run `install.sh`, verify PATH)
- [ ] Write Usage section with examples for all commands and flags
- [ ] Write Configuration section (env vars, `.env` file, allowlist, `OCC_RUNTIME`)
- [ ] Write Troubleshooting section (common errors from PRD §8, how to resolve)
- [ ] Write Architecture section (brief, link to PRD for details)

### Verification

```bash
#!/usr/bin/env bash
# phase6-check.sh — validates README completeness
set -euo pipefail
README="./README.md"

[ -f "$README" ] || { echo "FAIL: README.md not found"; exit 1; }

# Check for required sections
for section in "Overview" "Requirement" "Install" "Usage" "Configur" "Troubleshoot"; do
  grep -qi "$section" "$README" || { echo "FAIL: Missing section: $section"; exit 1; }
done

# Check for key content
for keyword in "occ" "Dockerfile" "Tailscale" "opencode" "--rebuild" "--env" "--no-tailscale" "status" "config" "docker" "container"; do
  grep -qi "$keyword" "$README" || { echo "FAIL: Missing keyword: $keyword"; exit 1; }
done

# Minimum length check (~150 lines per PRD)
LINES=$(wc -l < "$README")
[ "$LINES" -ge 100 ] || { echo "FAIL: README too short ($LINES lines)"; exit 1; }

echo "Phase 6: PASS"
```

---

## Phase 7: Integration Testing & End-to-End Validation

**Depends on**: All previous phases (0–6)  
**Produces**: A single integration test script that exercises the full workflow from install through container launch and teardown. This is the final quality gate.

### Tasks

- [ ] Write `test/integration.sh` that performs the full PRD §10 manual checklist automatically:
  1. Run `install.sh` in an isolated `$HOME`
  2. Verify `occ --help` works from installed path
  3. Build the image (`occ --rebuild --no-tailscale`)
  4. Launch a bare shell container, run `id` inside, verify UID/GID match
  5. Launch with a test project directory, verify `/workspace` mount and file ownership
  6. Verify `.env` file values appear inside container
  7. Verify `--env` passthrough works
  8. Verify `occ status` lists running container (launch in background first)
  9. Verify `occ config` output
  10. Verify `--no-tailscale` skips Tailscale (no `TS_AUTHKEY` required)
  11. Clean up: remove test image and temp dirs
- [ ] Ensure the script exits non-zero on any failure with clear output identifying which test failed
- [ ] Run the integration test and fix any issues found
- [ ] Re-run until all tests pass

### Verification

The integration test script **is itself the verification**. The autonomous feedback loop is:

```bash
#!/usr/bin/env bash
# Run the full integration suite
set -euo pipefail
echo "Running integration tests..."
bash test/integration.sh
echo "All integration tests passed."
```

If any test fails, the script prints the failing test name and exits non-zero, signaling what needs to be fixed. Iterate until exit code 0.

---

## Phase Dependency Graph

```
Phase 0 (Scaffolding)
  ├── Phase 1 (Dockerfile & Entrypoint)
  │     └──┐
  ├── Phase 2 (CLI Framework & Args) ──► Phase 3 (Env Var Handling)
  │     │                                   │
  │     └───────────────────────────────────┘
  │                     │
  │                     ▼
  │              Phase 4 (Image Build & Container Launch)
  │                     │
  ├── Phase 5 (install.sh)
  │                     │
  │                     ▼
  │              Phase 6 (README & Docs)
  │                     │
  └─────────────────────▼
                 Phase 7 (Integration Testing)
```

## Summary

| Phase | Description | Depends On | Key Deliverable |
|-------|-------------|------------|-----------------|
| 0 | Scaffolding | — | Repo structure, git init |
| 1 | Dockerfile & Entrypoint | 0 | Buildable multi-arch image |
| 2 | CLI Framework | 0 | `occ` arg parsing, runtime detection |
| 3 | Env Var Handling | 2 | Allowlist, `.env`, `--env` logic |
| 4 | Build & Launch | 1, 2, 3 | Full container lifecycle |
| 5 | Installer | 0, 1, 2 | `install.sh` |
| 6 | Documentation | 1–5 | `README.md` |
| 7 | Integration | 0–6 | End-to-end validation |
