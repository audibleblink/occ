#!/usr/bin/env bash
set -euo pipefail

# occ Integration Tests
# Performs full end-to-end validation of occ installation and functionality

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Temp directory for test isolation
TEST_TMPDIR=""
TEST_HOME=""
TEST_PROJECT=""

# Container cleanup list
CONTAINERS_TO_CLEANUP=()

# ============================================================================
# Utilities
# ============================================================================

pass() { 
  echo -e "${GREEN}PASS${NC}: $1"
  TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() { 
  echo -e "${RED}FAIL${NC}: $1"
  TESTS_FAILED=$((TESTS_FAILED + 1))
  if [[ "${FAIL_FAST:-}" == "1" ]]; then
    echo -e "\n${RED}Exiting early (FAIL_FAST=1)${NC}"
    cleanup
    exit 1
  fi
}

skip() { 
  echo -e "${YELLOW}SKIP${NC}: $1"
  TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
}

info() {
  echo -e "${BLUE}INFO${NC}: $1"
}

# ============================================================================
# Setup & Cleanup
# ============================================================================

setup() {
  echo "=== Setting up test environment ==="
  
  # Create isolated temp directory
  TEST_TMPDIR=$(mktemp -d)
  TEST_HOME="$TEST_TMPDIR/home"
  TEST_PROJECT="$TEST_TMPDIR/project"
  
  # Create fake home with required dirs
  mkdir -p "$TEST_HOME/.config/opencode"
  mkdir -p "$TEST_HOME/.local/bin"
  
  # Create test project directory
  mkdir -p "$TEST_PROJECT"
  echo "# Test Project" > "$TEST_PROJECT/README.md"
  
  # Create test .env file
  cat > "$TEST_PROJECT/.env" << 'EOF'
# Test environment file
TEST_VAR_FROM_DOTENV=hello-from-dotenv
ANOTHER_VAR=world
EOF

  echo "  Test home: $TEST_HOME"
  echo "  Test project: $TEST_PROJECT"
  echo ""
}

cleanup() {
  echo ""
  echo "=== Cleaning up ==="
  
  # Stop and remove any test containers
  for container_name in "${CONTAINERS_TO_CLEANUP[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$" 2>/dev/null; then
      info "Removing container: $container_name"
      docker rm -f "$container_name" 2>/dev/null || true
    fi
  done
  
  # Remove test image if it exists
  if docker image inspect "occ-workspace:latest" &>/dev/null 2>&1; then
    info "Removing test image: occ-workspace:latest"
    docker rmi -f "occ-workspace:latest" 2>/dev/null || true
  fi
  
  # Remove temp directories
  if [[ -n "$TEST_TMPDIR" && -d "$TEST_TMPDIR" ]]; then
    info "Removing temp directory: $TEST_TMPDIR"
    rm -rf "$TEST_TMPDIR"
  fi
  
  echo "Cleanup complete."
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

# ============================================================================
# Test Functions
# ============================================================================

test_docker_available() {
  echo "Test: Docker availability..."
  
  if ! command -v docker &>/dev/null; then
    skip "Docker not installed"
    return 1
  fi
  
  if ! docker info &>/dev/null; then
    skip "Docker daemon not running"
    return 1
  fi
  
  pass "Docker is available"
  return 0
}

test_install_script() {
  echo "Test: install.sh in isolated HOME..."
  
  # Run install.sh with isolated HOME
  if ! (cd "$PROJECT_ROOT" && HOME="$TEST_HOME" ./install.sh); then
    fail "install.sh failed to run"
    return 1
  fi
  
  # Verify Dockerfile installed
  if [[ ! -f "$TEST_HOME/.config/occ/Dockerfile" ]]; then
    fail "Dockerfile not installed to ~/.config/occ/"
    return 1
  fi
  
  # Verify occ installed
  if [[ ! -f "$TEST_HOME/.local/bin/occ" ]]; then
    fail "occ not installed to ~/.local/bin/"
    return 1
  fi
  
  # Verify occ is executable
  if [[ ! -x "$TEST_HOME/.local/bin/occ" ]]; then
    fail "occ not executable"
    return 1
  fi
  
  # Verify .gitignore created
  if [[ ! -f "$TEST_HOME/.config/occ/.gitignore" ]]; then
    fail ".gitignore not created"
    return 1
  fi
  
  pass "install.sh works correctly"
  return 0
}

test_occ_help() {
  echo "Test: occ --help from installed path..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  
  if [[ ! -x "$occ_path" ]]; then
    fail "occ not found at $occ_path"
    return 1
  fi
  
  # Run --help with isolated HOME
  local output
  if ! output=$(HOME="$TEST_HOME" "$occ_path" --help 2>&1); then
    fail "occ --help exited with error"
    return 1
  fi
  
  # Verify usage output
  if ! echo "$output" | grep -q "Usage"; then
    fail "occ --help doesn't show Usage"
    return 1
  fi
  
  if ! echo "$output" | grep -q -- "--rebuild"; then
    fail "occ --help doesn't mention --rebuild"
    return 1
  fi
  
  if ! echo "$output" | grep -q -- "--no-tailscale"; then
    fail "occ --help doesn't mention --no-tailscale"
    return 1
  fi
  
  pass "occ --help works from installed path"
  return 0
}

test_image_build() {
  echo "Test: Build image (occ --rebuild --no-tailscale)..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  
  # Build the image - this will take a while
  info "Building image (this may take several minutes)..."
  
  # We need to provide a command that exits immediately for the build-only test
  # The trick: we run with a project path but the build happens first
  # Actually, let's just verify the build command works by running occ and 
  # letting it build, then Ctrl+C (or use timeout)
  
  # Better approach: run a command that just exits immediately
  if ! HOME="$TEST_HOME" timeout 600 "$occ_path" --rebuild --no-tailscale "$TEST_PROJECT" -- echo "Build successful" 2>&1; then
    # Note: timeout returns 124 on timeout, command failure returns the command's exit code
    local exit_code=$?
    if [[ $exit_code -eq 124 ]]; then
      fail "Image build timed out after 10 minutes"
      return 1
    fi
    fail "Image build failed with exit code $exit_code"
    return 1
  fi
  
  # Verify image exists
  if ! docker image inspect "occ-workspace:latest" &>/dev/null; then
    fail "Image occ-workspace:latest not created"
    return 1
  fi
  
  pass "Image built successfully"
  return 0
}

test_uid_gid_mapping() {
  echo "Test: UID/GID mapping in container..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  local host_uid=$(id -u)
  local host_gid=$(id -g)
  
  # Run container with 'id' command
  local output
  if ! output=$(HOME="$TEST_HOME" "$occ_path" --no-tailscale -- id 2>&1); then
    fail "Failed to run container with id command"
    return 1
  fi
  
  # Verify UID matches
  if ! echo "$output" | grep -q "uid=${host_uid}"; then
    fail "UID mismatch: expected $host_uid, got: $output"
    return 1
  fi
  
  # Verify GID matches
  if ! echo "$output" | grep -q "gid=${host_gid}"; then
    fail "GID mismatch: expected $host_gid, got: $output"
    return 1
  fi
  
  pass "UID/GID mapping correct (uid=$host_uid, gid=$host_gid)"
  return 0
}

test_workspace_mount() {
  echo "Test: /workspace mount and file ownership..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  local host_uid=$(id -u)
  
  # Create a test file in the project
  echo "test content" > "$TEST_PROJECT/testfile.txt"
  
  # Run container and check workspace
  local output
  if ! output=$(HOME="$TEST_HOME" "$occ_path" --no-tailscale "$TEST_PROJECT" -- ls -la /workspace 2>&1); then
    fail "Failed to list /workspace"
    return 1
  fi
  
  # Verify our files are there
  if ! echo "$output" | grep -q "README.md"; then
    fail "/workspace doesn't contain README.md"
    return 1
  fi
  
  if ! echo "$output" | grep -q "testfile.txt"; then
    fail "/workspace doesn't contain testfile.txt"
    return 1
  fi
  
  # Check file ownership (should be user, matching host UID)
  local owner_output
  if ! owner_output=$(HOME="$TEST_HOME" "$occ_path" --no-tailscale "$TEST_PROJECT" -- stat -c '%u' /workspace/testfile.txt 2>&1); then
    fail "Failed to stat file ownership"
    return 1
  fi
  
  if ! echo "$owner_output" | grep -q "$host_uid"; then
    fail "File ownership incorrect: expected $host_uid, got: $owner_output"
    return 1
  fi
  
  pass "/workspace mount and ownership correct"
  return 0
}

test_dotenv_passthrough() {
  echo "Test: .env file values appear inside container..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  
  # Run container and echo the env var from .env
  local output
  if ! output=$(HOME="$TEST_HOME" "$occ_path" --no-tailscale "$TEST_PROJECT" -- printenv TEST_VAR_FROM_DOTENV 2>&1); then
    fail "Failed to read TEST_VAR_FROM_DOTENV"
    return 1
  fi
  
  if ! echo "$output" | grep -q "hello-from-dotenv"; then
    fail ".env var not passed: expected 'hello-from-dotenv', got: $output"
    return 1
  fi
  
  pass ".env file values passed to container"
  return 0
}

test_env_flag_passthrough() {
  echo "Test: --env flag passthrough..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  
  # Set a custom env var on host
  export CUSTOM_TEST_VAR="my-custom-value-12345"
  
  # Run container with --env and check the value
  local output
  if ! output=$(HOME="$TEST_HOME" "$occ_path" --no-tailscale --env CUSTOM_TEST_VAR -- printenv CUSTOM_TEST_VAR 2>&1); then
    fail "Failed to read CUSTOM_TEST_VAR"
    return 1
  fi
  
  if ! echo "$output" | grep -q "my-custom-value-12345"; then
    fail "--env passthrough failed: expected 'my-custom-value-12345', got: $output"
    return 1
  fi
  
  unset CUSTOM_TEST_VAR
  
  pass "--env flag passthrough works"
  return 0
}

test_occ_config() {
  echo "Test: occ config output..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  
  local output
  if ! output=$(HOME="$TEST_HOME" "$occ_path" config 2>&1); then
    fail "occ config failed"
    return 1
  fi
  
  # Should mention config directory
  if ! echo "$output" | grep -q "occ"; then
    fail "occ config doesn't mention occ directory"
    return 1
  fi
  
  # Should show Dockerfile exists
  if ! echo "$output" | grep -q "Dockerfile"; then
    fail "occ config doesn't show Dockerfile"
    return 1
  fi
  
  pass "occ config works correctly"
  return 0
}

test_occ_status() {
  echo "Test: occ status lists running containers..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  
  # First, run status with no containers - should work without error
  local output
  if ! output=$(HOME="$TEST_HOME" "$occ_path" status 2>&1); then
    fail "occ status failed"
    return 1
  fi
  
  # Should mention "running" or "no occ containers"
  if ! echo "$output" | grep -qi "occ\|container\|running"; then
    fail "occ status output unexpected: $output"
    return 1
  fi
  
  pass "occ status works correctly"
  return 0
}

test_no_tailscale_skips() {
  echo "Test: --no-tailscale skips Tailscale (no TS_AUTHKEY required)..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  
  # Ensure TS_AUTHKEY is NOT set
  unset TS_AUTHKEY 2>/dev/null || true
  
  # Run container with --no-tailscale - should work without TS_AUTHKEY
  local output
  if ! output=$(HOME="$TEST_HOME" "$occ_path" --no-tailscale -- echo "Tailscale skipped successfully" 2>&1); then
    fail "--no-tailscale still requires TS_AUTHKEY or failed"
    return 1
  fi
  
  if ! echo "$output" | grep -q "Tailscale skipped successfully\|Tailscale disabled\|Tailscale skipped"; then
    fail "--no-tailscale didn't skip properly: $output"
    return 1
  fi
  
  pass "--no-tailscale correctly skips Tailscale setup"
  return 0
}

test_container_tools_installed() {
  echo "Test: Container has required tools installed..."
  
  local occ_path="$TEST_HOME/.local/bin/occ"
  
  local tools=("bash" "git" "nvim" "tmux" "zsh" "jq" "rg" "fzf" "node" "npm" "python3" "curl" "wget" "yq" "mise" "uv" "opencode" "tailscale")
  local missing_tools=()
  
  for tool in "${tools[@]}"; do
    if ! HOME="$TEST_HOME" "$occ_path" --no-tailscale -- which "$tool" &>/dev/null; then
      missing_tools+=("$tool")
    fi
  done
  
  if [[ ${#missing_tools[@]} -gt 0 ]]; then
    fail "Missing tools in container: ${missing_tools[*]}"
    return 1
  fi
  
  pass "All required tools installed in container"
  return 0
}

# ============================================================================
# Main
# ============================================================================

main() {
  echo "========================================"
  echo "  occ Integration Test Suite"
  echo "========================================"
  echo ""
  
  # Setup
  setup
  
  # Check Docker first - if not available, skip most tests
  local docker_available=true
  test_docker_available || docker_available=false
  
  echo ""
  echo "=== Running Tests ==="
  echo ""
  
  # Test 1: install.sh (doesn't need Docker)
  test_install_script
  
  # Test 2: occ --help (doesn't need Docker)
  test_occ_help
  
  # Test 3: occ config (doesn't need Docker)
  test_occ_config
  
  # The remaining tests require Docker
  if [[ "$docker_available" == false ]]; then
    echo ""
    echo -e "${YELLOW}Skipping Docker-dependent tests (Docker not available)${NC}"
    skip "Image build (requires Docker)"
    skip "UID/GID mapping (requires Docker)"
    skip "Workspace mount (requires Docker)"
    skip ".env passthrough (requires Docker)"
    skip "--env passthrough (requires Docker)"
    skip "occ status with containers (requires Docker)"
    skip "--no-tailscale (requires Docker)"
    skip "Container tools (requires Docker)"
  else
    # Test 4: Build image
    if ! test_image_build; then
      echo -e "${YELLOW}Image build failed, skipping remaining Docker tests${NC}"
    else
      # Test 5: UID/GID mapping
      test_uid_gid_mapping
      
      # Test 6: Workspace mount
      test_workspace_mount
      
      # Test 7: .env passthrough
      test_dotenv_passthrough
      
      # Test 8: --env passthrough
      test_env_flag_passthrough
      
      # Test 9: occ status
      test_occ_status
      
      # Test 10: --no-tailscale
      test_no_tailscale_skips
      
      # Test 11: Container tools
      test_container_tools_installed
    fi
  fi
  
  # Summary
  echo ""
  echo "========================================"
  echo "  Test Summary"
  echo "========================================"
  echo -e "  ${GREEN}Passed${NC}:  $TESTS_PASSED"
  echo -e "  ${RED}Failed${NC}:  $TESTS_FAILED"
  echo -e "  ${YELLOW}Skipped${NC}: $TESTS_SKIPPED"
  echo "========================================"
  echo ""
  
  if [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
  fi
  
  echo -e "${GREEN}All tests passed!${NC}"
  exit 0
}

main "$@"
