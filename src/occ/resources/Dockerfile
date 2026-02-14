# occ Development Container
# Base image for OpenCode Container CLI

FROM python:3.12-slim

# Install basic development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    vim \
    neovim \
    tmux \
    ripgrep \
    fzf \
    jq \
    build-essential \
    ca-certificates \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

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
