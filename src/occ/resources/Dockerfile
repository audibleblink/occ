# occ Development Container
# Multi-arch Dockerfile for ephemeral dev containers
# Base: Wolfi (glibc-based minimal Linux)

FROM cgr.dev/chainguard/wolfi-base:latest

# Build args for multi-arch support (automatically set by docker buildx)
ARG TARGETARCH

# Install system packages via apk
RUN apk update && apk add --no-cache \
    bash \
    build-base \
    ca-certificates \
    coreutils \
    curl \
    fzf \
    git \
    gosu \
    jq \
    neovim \
    ripgrep \
    shadow \
    tailscale \
    tmux \
    wget \
    && rm -rf /var/cache/apk/*

# Create non-root user early
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN groupadd -g ${HOST_GID} developer || true && \
    useradd -m -u ${HOST_UID} -g ${HOST_GID} -s /bin/bash developer || true

# Switch to developer for installations
USER developer

# Ensure ~/.local/bin and ~/.opencode/bin are in PATH for developer
ENV PATH="/home/developer/.local/bin:/home/developer/.opencode/bin:${PATH}"

# Create config directories so mounts don't create them as root
RUN mkdir -p ~/.config/mise ~/.config/opencode ~/.local/share/opencode ~/.local/state/opencode

# Install opencode via install script (installs to ~/.local/bin or ~/.opencode/bin)
RUN curl -fsSL https://opencode.ai/install | bash

# Install mise via install script (installs to ~/.local/bin by default)
RUN curl -fsSL https://mise.run | bash

# Set up working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
