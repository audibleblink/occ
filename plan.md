# Execution Plan: Implement `occ shell --path/-p` with Shared Container Lifecycle

## Overview

This plan implements the PRD for refactoring `cli.py` to extract container lifecycle logic into a reusable helper function, enabling the `shell` command to support the same `--path/-p` option as the main command.

**File to modify:** `src/occ/cli.py`

---

## Phase 1: Extract `ensure_container_running()` Helper Function

**Goal:** Create the shared helper function that encapsulates container lifecycle logic.

**Depends on:** None (foundational phase)

### Tasks

- [x] Create `ensure_container_running()` function signature with all parameters:
  - `path: Path | None = None`
  - `rebuild: bool = False`
  - `env: list[str] | None = None`
  - `verbose: bool = False`
  - `quiet: bool = False`
- [x] Extract path resolution and validation logic from `run_container_logic()`
- [x] Extract config initialization and loading logic
- [x] Extract Docker availability check
- [x] Extract container name determination via `sanitize_container_name()`
- [x] Extract image rebuild logic (checking `needs_rebuild()`, `image_exists()`, `build_image()`)
- [x] Extract container status handling and prompts
- [x] Extract container creation/startup logic
- [x] Return container name string on success
- [x] Add comprehensive docstring with Args, Returns, and Raises sections

### Verification

```bash
# Run syntax check
python -m py_compile src/occ/cli.py

# Run the CLI help to ensure it still loads
python -m occ.cli --help

# Verify the helper function exists and is importable
python -c "from occ.cli import ensure_container_running; print('Helper function exists:', ensure_container_running.__doc__[:50])"
```

### Exit Criteria

- `ensure_container_running()` function exists in `cli.py`
- Function has complete docstring
- CLI module imports without errors
- `occ --help` displays correctly

---

## Phase 2: Refactor `run_container_logic()` to Use Helper

**Goal:** Simplify `run_container_logic()` by delegating to the new helper.

**Depends on:** Phase 1

### Tasks

- [x] Modify `run_container_logic()` to call `ensure_container_running()` for container setup
- [x] Keep only attachment logic (`attach_to_container(container_name)`) in `run_container_logic()`
- [x] Keep stop-on-exit behavior handling in `run_container_logic()` (respects `keep_alive` flag)
- [x] Reload config after helper returns for stop-on-exit check
- [x] Ensure all existing main command behavior is preserved

### Verification

```bash
# Run syntax check
python -m py_compile src/occ/cli.py

# Test main command help still works
python -m occ.cli --help

# Test main command with --version
python -m occ.cli --version

# Integration test: Run occ in a test directory (requires Docker)
# This should work exactly as before
cd /tmp && mkdir -p test-occ-phase2 && cd test-occ-phase2
occ --help  # Should show all options

# If Docker available, test container creation works
# occ -p /tmp/test-occ-phase2 --rebuild
```

### Exit Criteria

- `run_container_logic()` is significantly shorter (uses helper)
- Main command (`occ`) behavior unchanged
- `occ --help` shows correct options
- `occ --version` works
- No duplicate code between helper and main logic

---

## Phase 3: Update `shell()` Command with New API

**Goal:** Replace the positional `project` argument with `--path/-p` option and add other flags.

**Depends on:** Phase 1, Phase 2

### Tasks

- [x] Remove positional `project: Optional[str]` argument from `shell()`
- [x] Add `--path/-p` option (Path type, defaults to None/cwd)
- [x] Add `--rebuild` option (bool, defaults to False)
- [x] Add `--env/-e` option (list[str], repeatable)
- [x] Add `--verbose/-v` option (bool)
- [x] Add `--quiet/-q` option (bool)
- [x] Update function to call `ensure_container_running()` with new parameters
- [x] Update attach call to use `/bin/bash` as command
- [x] Add stop-on-exit behavior (respects config, no `keep_alive` option)
- [x] Update docstring with new usage examples
- [x] Remove `resolve_container_name()` call (no longer needed for shell)

### Verification

```bash
# Run syntax check
python -m py_compile src/occ/cli.py

# Test shell command help
python -m occ.cli shell --help

# Verify new options are present
python -m occ.cli shell --help | grep -E "(-p|--path)"
python -m occ.cli shell --help | grep -E "(-e|--env)"
python -m occ.cli shell --help | grep -E "(-v|--verbose)"
python -m occ.cli shell --help | grep -E "(-q|--quiet)"
python -m occ.cli shell --help | grep -E "--rebuild"

# Verify positional argument is removed
! python -m occ.cli shell --help | grep -E "PROJECT"

# Integration test (requires Docker):
# occ shell --help
# occ shell -p /tmp/test-occ-phase2
```

### Exit Criteria

- `occ shell --help` shows `--path/-p`, `--rebuild`, `--env/-e`, `--verbose/-v`, `--quiet/-q`
- `occ shell --help` does NOT show positional PROJECT argument
- Shell command uses `ensure_container_running()` helper
- Shell command attaches with `/bin/bash`
- Shell command respects `stop_on_exit` config

---

## Phase 4: Update Help Text and Documentation

**Goal:** Update docstrings and examples to reflect the new shell command API.

**Depends on:** Phase 3

### Tasks

- [ ] Update main command docstring examples to include new shell usage
- [ ] Ensure shell command docstring has clear examples:
  - `occ shell` (bash for cwd)
  - `occ shell -p ~/myproject` (bash for path)
  - `occ shell --rebuild` (force rebuild)
- [ ] Verify all help text is consistent

### Verification

```bash
# Check main help shows updated examples
python -m occ.cli --help

# Check shell help shows correct examples
python -m occ.cli shell --help

# Verify examples in help text
python -m occ.cli --help | grep "occ shell"
python -m occ.cli shell --help | grep "occ shell -p"
```

### Exit Criteria

- Main command help shows `occ shell -p ~/proj` example
- Shell command help shows correct usage examples
- All documentation is internally consistent

---

## Phase 5: Cleanup and Final Verification

**Goal:** Remove unused code and perform comprehensive testing.

**Depends on:** Phase 4

### Tasks

- [ ] Review `resolve_container_name()` - determine if still needed by other commands
- [ ] If `resolve_container_name()` is only used by old shell command, consider removal or update
- [ ] Run full syntax validation
- [ ] Run type checking if available (mypy)
- [ ] Perform manual end-to-end testing of all commands

### Verification

```bash
# Full syntax check
python -m py_compile src/occ/cli.py

# Type checking (if mypy installed)
mypy src/occ/cli.py --ignore-missing-imports 2>/dev/null || echo "mypy not available, skipping"

# Verify all commands work
python -m occ.cli --help
python -m occ.cli --version
python -m occ.cli status --help
python -m occ.cli stop --help
python -m occ.cli shell --help
python -m occ.cli config --help

# Verify no Python errors on import
python -c "from occ.cli import app, ensure_container_running, run_container_logic; print('All imports successful')"

# Check for any obvious issues
python -c "
from occ.cli import app
import typer
# Verify commands exist
commands = [c.name for c in app.registered_commands]
print('Registered commands:', commands)
assert 'status' in commands
assert 'shell' in commands
assert 'stop' in commands
print('All required commands present')
"
```

### Exit Criteria

- No syntax errors
- All CLI commands accessible via help
- No unused imports or dead code
- Type checking passes (if available)
- All acceptance criteria from PRD met:
  1. ✓ `occ shell` with no arguments creates container for cwd
  2. ✓ `occ shell -p /path` creates container for specified path
  3. ✓ `occ shell --rebuild` forces image rebuild
  4. ✓ `occ shell -e VAR=value` passes env vars
  5. ✓ `occ shell -v` shows verbose output
  6. ✓ `occ shell -q` minimizes output
  7. ✓ Running container prompts work identically
  8. ✓ `stop_on_exit` config is respected
  9. ✓ Main command behavior unchanged
  10. ✓ No duplicate code (uses shared helper)

---

## Summary

| Phase | Description | Depends On | Verification Method |
|-------|-------------|------------|---------------------|
| 1 | Extract `ensure_container_running()` helper | None | Syntax check, import test |
| 2 | Refactor `run_container_logic()` | Phase 1 | CLI help, version check |
| 3 | Update `shell()` command API | Phases 1, 2 | Shell help, option verification |
| 4 | Update help text and documentation | Phase 3 | Help text inspection |
| 5 | Cleanup and final verification | Phase 4 | Full command suite test |

**Total estimated changes:** ~150 lines modified in `src/occ/cli.py`

**Risk mitigation:** Each phase leaves the codebase in a working state. If any phase fails verification, rollback is straightforward.
