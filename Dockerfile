# Kept in sync with the embedded DOCKERFILE constant in ./clankbox.
# The launcher builds from its embedded copy so a single installed binary works.
FROM debian:bookworm-slim@sha256:7b140f374b289a7c2befc338f42ebe6441b7ea838a042bbd5acbfca6ec875818

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/clank \
    PATH=/usr/local/bin:/usr/bin:/bin:/home/clank/.local/bin \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    OPENCODE_DISABLE_AUTOUPDATE=1

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
