FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/clank \
    PATH=/usr/local/bin:/usr/bin:/bin \
    OPENCODE_DISABLE_AUTOUPDATE=1

# Lean base tools (avoid Debian npm: it pulls webpack/eslint and balloons the image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    file \
    findutils \
    g++ \
    gawk \
    git \
    grep \
    jq \
    less \
    make \
    nano \
    openssh-client \
    patch \
    procps \
    python3 \
    python3-pip \
    python3-venv \
    ripgrep \
    sed \
    tar \
    unzip \
    wget \
    xz-utils \
    zip \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Official Node binary (includes npm/npx, much smaller than Debian npm)
ARG NODE_VERSION=22.17.0
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    | tar -xJ -C /usr/local --strip-components=1 \
    && npm cache clean --force \
    && rm -rf /tmp/* /root/.npm \
    && node --version && npm --version

# UID 1000 is remapped to the host user via podman --userns keep-id:uid=1000,gid=1000
RUN echo 'clank:x:1000:1000:clank:/home/clank:/bin/bash' >> /etc/passwd \
    && echo 'clank:x:1000:' >> /etc/group \
    && mkdir -p /home/clank/.local/share/opencode \
        /home/clank/.config/opencode \
        /workspace \
    && chown -R 1000:1000 /home/clank /workspace

# Standalone opencode binary
USER clank
WORKDIR /home/clank
RUN curl -fsSL https://opencode.ai/install | bash \
    && test -x /home/clank/.opencode/bin/opencode \
    && /home/clank/.opencode/bin/opencode --version

USER root
RUN install -m 0755 /home/clank/.opencode/bin/opencode /usr/local/bin/opencode \
    && rm -rf /home/clank/.opencode \
    && chown -R 1000:1000 /home/clank

WORKDIR /workspace
USER clank

CMD ["sleep", "infinity"]
