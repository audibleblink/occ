# occ Development Container
# Multi-arch Dockerfile for ephemeral dev containers
# Base: Wolfi (glibc-based minimal Linux)

FROM cgr.dev/chainguard/wolfi-base:latest

# Build args for multi-arch support (automatically set by docker buildx)
ARG TARGETARCH

# Install system packages via apk
RUN apk update && apk add --no-cache \
    bash \
    coreutils \
    shadow \
    ca-certificates \
    curl \
    wget \
    git \
    vim \
    neovim \
    tmux \
    jq \
    ripgrep \
    fzf \
    build-base \
    gosu \
    && rm -rf /var/cache/apk/*

# Install opencode via install script
RUN curl -fsSL https://opencode.ai/install | bash && \
    mv /root/.local/bin/opencode /usr/local/bin/opencode 2>/dev/null || \
    mv /root/.opencode/bin/opencode /usr/local/bin/opencode 2>/dev/null || \
    true && \
    chmod +x /usr/local/bin/opencode 2>/dev/null || true

# Install mise via install script
ENV MISE_INSTALL_PATH=/usr/local/bin/mise
RUN curl -fsSL https://mise.run | bash && \
    chmod +x /usr/local/bin/mise

# Set up working directory
WORKDIR /workspace

# Create non-root user
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN groupadd -g ${HOST_GID} developer || true && \
    useradd -m -u ${HOST_UID} -g ${HOST_GID} -s /bin/bash developer || true

# Set default user
USER developer

# Default command
CMD ["/bin/bash"]
