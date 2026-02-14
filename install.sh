#!/usr/bin/env bash
set -euo pipefail

# install.sh - Install occ to user local directories

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

error() {
  echo -e "${RED}Error:${NC} $1" >&2
  exit 1
}

warn() {
  echo -e "${YELLOW}Warning:${NC} $1" >&2
}

info() {
  echo -e "${GREEN}==>${NC} $1"
}

# Task 1: Verify script is run from the source directory
if [[ ! -f "./Dockerfile" ]]; then
  error "Dockerfile not found in current directory. Please run install.sh from the occ source directory."
fi

if [[ ! -f "./occ" ]]; then
  error "occ script not found in current directory. Please run install.sh from the occ source directory."
fi

# Task 2: Create ~/.config/occ/ directory
CONFIG_DIR="$HOME/.config/occ"
info "Creating config directory: $CONFIG_DIR"
mkdir -p "$CONFIG_DIR"

# Task 3: Copy ./Dockerfile → ~/.config/occ/Dockerfile
info "Copying Dockerfile to $CONFIG_DIR/Dockerfile"
cp "./Dockerfile" "$CONFIG_DIR/Dockerfile"

# Task 4: Create ~/.config/occ/.gitignore
info "Creating .gitignore in $CONFIG_DIR"
cat > "$CONFIG_DIR/.gitignore" << 'EOF'
*.key
tailscale-*
.env
EOF

# Task 5: Create ~/.local/bin/ if it doesn't exist
BIN_DIR="$HOME/.local/bin"
info "Creating bin directory: $BIN_DIR"
mkdir -p "$BIN_DIR"

# Task 6: Copy ./occ → ~/.local/bin/occ
info "Installing occ to $BIN_DIR/occ"
cp "./occ" "$BIN_DIR/occ"

# Task 7: chmod +x ~/.local/bin/occ
chmod +x "$BIN_DIR/occ"

# Task 8: Check if ~/.local/bin is in $PATH; warn if not
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  warn "$BIN_DIR is not in your PATH"
fi

# Task 9: Print post-install message
echo ""
echo "Installation complete."
echo ""
echo "Setup:"
echo "  1. Ensure ~/.local/bin is in your PATH"
echo "  2. Export your Tailscale auth key:"
echo "     export TS_AUTHKEY=\"tskey-auth-xxxxx\""
echo ""
echo "Usage:"
echo "  occ                         Start bash in container"
echo "  occ ~/Code/project          Start OpenCode in project"
echo "  occ --rebuild               Rebuild container image"
echo "  occ --env MY_VAR ~/proj     Pass additional env var"
echo "  occ --no-tailscale          Run without Tailscale"
echo "  occ status                  List running containers"
echo "  occ config                  Show config directory"
echo ""
echo "First run will build the container image (5-10 minutes)."
