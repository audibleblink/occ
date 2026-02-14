# occ - OpenCode Container
# Multi-arch Dockerfile for ephemeral Tailscale-connected dev containers
# Base: Wolfi (glibc-based minimal Linux)

FROM cgr.dev/chainguard/wolfi-base:latest

# Build args for multi-arch support (automatically set by docker buildx)
ARG TARGETARCH

# Install system packages via apk
RUN apk update && apk add --no-cache \
    bash \
    coreutils \
    shadow \
    sudo \
    ca-certificates \
    curl \
    wget \
    git \
    neovim \
    zsh \
    tmux \
    jq \
    ripgrep \
    fzf \
    nodejs \
    npm \
    python3 \
    build-base \
    gosu \
    && rm -rf /var/cache/apk/*

# Install Tailscale (architecture-aware)
# Using stable release from pkgs.tailscale.com
ARG TAILSCALE_VERSION=1.80.3
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) TS_ARCH="amd64" ;; \
        arm64) TS_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    curl -fsSL "https://pkgs.tailscale.com/stable/tailscale_${TAILSCALE_VERSION}_${TS_ARCH}.tgz" -o /tmp/tailscale.tgz; \
    tar -xzf /tmp/tailscale.tgz -C /tmp; \
    cp /tmp/tailscale_*/tailscale /usr/local/bin/tailscale; \
    cp /tmp/tailscale_*/tailscaled /usr/local/bin/tailscaled; \
    chmod +x /usr/local/bin/tailscale /usr/local/bin/tailscaled; \
    rm -rf /tmp/tailscale*

# Install yq (architecture-aware)
ARG YQ_VERSION=v4.44.3
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) YQ_ARCH="amd64" ;; \
        arm64) YQ_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_${YQ_ARCH}" -o /usr/local/bin/yq; \
    chmod +x /usr/local/bin/yq

# Create default non-root placeholder user (UID 1000)
# The entrypoint will modify this user's UID/GID to match the host
RUN groupadd -g 1000 user && \
    useradd -m -u 1000 -g user -s /bin/bash user && \
    echo "user ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/user && \
    chmod 0440 /etc/sudoers.d/user

# Install opencode via install script
# Run as user since the installer expects a home directory
RUN curl -fsSL https://opencode.ai/install | bash && \
    mv /root/.local/bin/opencode /usr/local/bin/opencode 2>/dev/null || \
    mv /root/.opencode/bin/opencode /usr/local/bin/opencode 2>/dev/null || \
    true && \
    chmod +x /usr/local/bin/opencode 2>/dev/null || true

# Install mise via install script
ENV MISE_INSTALL_PATH=/usr/local/bin/mise
RUN curl -fsSL https://mise.run | bash && \
    chmod +x /usr/local/bin/mise

# Install uv via install script
ENV UV_INSTALL_DIR=/usr/local/bin
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    chmod +x /usr/local/bin/uv 2>/dev/null || \
    (mv /root/.local/bin/uv /usr/local/bin/uv && chmod +x /usr/local/bin/uv) || \
    true

# Create entrypoint script
RUN cat > /entrypoint.sh << 'ENTRYPOINT_EOF'
#!/bin/bash
set -euo pipefail

# Default values
HOST_UID="${HOST_UID:-1000}"
HOST_GID="${HOST_GID:-1000}"
USERNAME="user"
HOMEDIR="/home/${USERNAME}"

# --- User Setup ---
# Modify existing user/group to match host UID/GID

# Get current UID/GID
CURRENT_UID=$(id -u "${USERNAME}" 2>/dev/null || echo "0")
CURRENT_GID=$(grep "^${USERNAME}:" /etc/group | cut -d: -f3 || echo "0")

# Modify group if GID differs
if [ "${CURRENT_GID}" != "${HOST_GID}" ]; then
    # Check if a group with HOST_GID already exists
    EXISTING_GROUP=$(grep ":${HOST_GID}:" /etc/group | cut -d: -f1 || true)
    if [ -n "${EXISTING_GROUP}" ] && [ "${EXISTING_GROUP}" != "${USERNAME}" ]; then
        groupmod -g 9999 "${EXISTING_GROUP}" 2>/dev/null || true
    fi
    groupmod -g "${HOST_GID}" "${USERNAME}"
fi

# Modify user if UID differs
if [ "${CURRENT_UID}" != "${HOST_UID}" ]; then
    # Check if a user with HOST_UID already exists
    EXISTING_USER=$(grep ":x:${HOST_UID}:" /etc/passwd | cut -d: -f1 || true)
    if [ -n "${EXISTING_USER}" ] && [ "${EXISTING_USER}" != "${USERNAME}" ]; then
        usermod -u 9999 "${EXISTING_USER}" 2>/dev/null || true
    fi
    usermod -u "${HOST_UID}" "${USERNAME}"
fi

# Fix ownership on home directory
chown -R "${HOST_UID}:${HOST_GID}" "${HOMEDIR}"

# Ensure .local/bin exists for user tools
mkdir -p "${HOMEDIR}/.local/bin"
chown -R "${HOST_UID}:${HOST_GID}" "${HOMEDIR}/.local"

# --- Tailscale Setup (Conditional) ---
if [ -n "${TS_AUTHKEY:-}" ] && [ "${NO_TAILSCALE:-0}" != "1" ]; then
    echo "Starting Tailscale..."
    
    # Start tailscaled in background with userspace networking
    /usr/local/bin/tailscaled \
        --tun=userspace-networking \
        --state=/tmp/tailscale.state \
        --socket=/tmp/tailscale.sock &
    
    TAILSCALED_PID=$!
    
    # Wait for tailscaled socket to be ready
    SOCKET_TIMEOUT=10
    SOCKET_ELAPSED=0
    while [ ! -S /tmp/tailscale.sock ] && [ ${SOCKET_ELAPSED} -lt ${SOCKET_TIMEOUT} ]; do
        sleep 1
        SOCKET_ELAPSED=$((SOCKET_ELAPSED + 1))
    done
    
    if [ ! -S /tmp/tailscale.sock ]; then
        echo "ERROR: tailscaled socket not ready after ${SOCKET_TIMEOUT}s"
        exit 1
    fi
    
    # Bring up Tailscale with auth key
    echo "Connecting to Tailscale network..."
    if ! /usr/local/bin/tailscale \
        --socket=/tmp/tailscale.sock \
        up \
        --authkey="${TS_AUTHKEY}" \
        --accept-routes \
        --timeout=30s; then
        echo "ERROR: Tailscale connection failed"
        exit 1
    fi
    
    # Verify connection with timeout
    TS_TIMEOUT=30
    TS_ELAPSED=0
    while [ ${TS_ELAPSED} -lt ${TS_TIMEOUT} ]; do
        STATUS=$(/usr/local/bin/tailscale --socket=/tmp/tailscale.sock status 2>/dev/null || echo "")
        if echo "${STATUS}" | grep -q "authenticated\|online\|100\." ; then
            echo "Tailscale connected successfully"
            break
        fi
        sleep 1
        TS_ELAPSED=$((TS_ELAPSED + 1))
    done
    
    if [ ${TS_ELAPSED} -ge ${TS_TIMEOUT} ]; then
        echo "ERROR: Tailscale connection timeout after ${TS_TIMEOUT}s"
        /usr/local/bin/tailscale --socket=/tmp/tailscale.sock status || true
        exit 1
    fi
elif [ "${NO_TAILSCALE:-0}" = "1" ]; then
    echo "Tailscale disabled (NO_TAILSCALE=1)"
elif [ -z "${TS_AUTHKEY:-}" ]; then
    echo "Tailscale skipped (no TS_AUTHKEY set)"
fi

# --- Exec as User ---
# If no command provided, default to bash
if [ $# -eq 0 ]; then
    set -- /bin/bash
fi

# Execute the command as the configured user
exec gosu "${USERNAME}" "$@"
ENTRYPOINT_EOF

RUN chmod +x /entrypoint.sh

# Set working directory
WORKDIR /workspace

# Set entrypoint and default command
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/bash"]
