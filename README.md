# clankbox

A container for safer vibecoding. Runs [opencode](https://opencode.ai) in a reusable podman container bound to your current directory.

## Requirements

- Python 3.10+
- [podman](https://podman.io/)
- network access to build the image and for tools inside the container

## Install

```bash
# from this repo
chmod +x clankbox
ln -s "$(pwd)/clankbox" ~/.local/bin/clankbox   # or any directory on your PATH
```

First run builds the image automatically.

## Usage

```bash
cd /path/to/your/project
clankbox                 # start opencode (creates/starts container if needed)
```

From another terminal in the same project directory:

```bash
clankbox                 # joins the same container
clankbox shell           # bash in the same container
```

Manage containers:

```bash
clankbox list            # all clankbox containers
clankbox stop            # stop this directory's container
clankbox stop --all
clankbox rm              # remove this directory's container
clankbox rm --all        # remove every clankbox container
clankbox build           # rebuild the image
```

Pass arguments through to opencode:

```bash
clankbox --continue
clankbox run "explain this repo"
```

## Design

| Concern | Approach |
|--------|----------|
| Workspace | Current directory bind-mounted at `/workspace` |
| Identity | One container name per absolute path hash |
| Reuse | Container kept with `sleep infinity`; sessions use `podman exec` |
| Network | Default podman networking (on) |
| Disk | Shared slim image; no named volumes; `rm` drops container layer |
| Host auth | Mounts `~/.local/share/opencode/auth.json`, `~/.config/opencode`, `~/.gitconfig`, `~/.ssh` (read-only) when present |
| API keys | Forwards common `*_API_KEY` / `GITHUB_TOKEN` env vars if set |

Containers are labeled `clankbox=1` so list/rm can find them. The host wrapper is Python 3 (stdlib only).

## Image contents

Debian bookworm slim plus: git, curl, wget, jq, ripgrep, python3, node/npm, make/g++, openssh-client, zip/unzip, and the opencode binary.
