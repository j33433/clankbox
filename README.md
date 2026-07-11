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
| API keys | Forwards every `*_API_KEY` env var, plus `GITHUB_TOKEN` / `GH_TOKEN`, if set |

Containers are labeled `clankbox=1` so list/rm can find them. The host wrapper is Python 3 (stdlib only).

## Concurrent terminals

Clankbox uses advisory locks in `~/.local/state/clankbox/locks` (or
`$XDG_STATE_HOME/clankbox/locks`) to serialize image builds and container
lifecycle operations. Starting sessions from multiple terminals in the same
workspace is safe: only one can create or start its shared container.

The locks are released before `podman exec`, so sessions can run concurrently.
They do not coordinate changes inside the shared workspace or container home;
agents can still conflict when editing files, running Git commands, or changing
dependencies. `stop` and `rm` remain destructive commands and can end active
sessions by design.

## Image contents

Debian bookworm slim plus: git, curl, wget, jq, ripgrep, python3, node/npm, make/g++, openssh-client, zip/unzip, sudo, and the opencode binary.

The `clank` user has passwordless `sudo`, so the agent can install extra packages (e.g. `sudo apt install ...`). Under rootless podman this is isolated from host root. Packages persist in that directory's container until `clankbox rm`.
