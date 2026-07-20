FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/clank \
    PATH=/usr/local/bin:/usr/bin:/bin:/home/clank/.local/bin \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    OPENCODE_DISABLE_AUTOUPDATE=1

# Lean base tools. Node/npm are intentionally not from Debian (it pulls
# webpack/eslint and balloons the image); clankbox provisions the official
# Node binary into each container instead.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    bzip2 \
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
    sudo \
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

# Node.js and opencode are not baked into the image. They are provisioned into
# each container by 'clankbox init' (the same code path as 'clankbox update'),
# so a fresh container always gets the current LTS Node and the latest
# opencode without rebuilding the image.

# UID 1000 is remapped to the host user via podman --userns keep-id:uid=1000,gid=1000
# Passwordless sudo lets the agent install project packages inside the container;
# rootless podman keeps this isolated from host root.
RUN echo 'clank:x:1000:1000:clank:/home/clank:/bin/bash' >> /etc/passwd \
    && echo 'clank:x:1000:' >> /etc/group \
    && echo 'clank:!:19000:0:99999:7:::' >> /etc/shadow \
    && echo 'clank ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/clank \
    && chmod 0440 /etc/sudoers.d/clank \
    && mkdir -p /home/clank/.local/share/opencode \
        /home/clank/.config/opencode \
        /workspace \
    && chown -R 1000:1000 /home/clank /workspace

WORKDIR /workspace
USER clank

CMD ["sleep", "infinity"]
