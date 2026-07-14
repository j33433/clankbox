# clankbox

![clankbox logo](logo/logo.png)

A container for safer vibecoding. Runs [opencode](https://opencode.ai) in a reusable podman container bound to your current directory.

## Why run opencode in a container?

An autonomous agent runs shell commands and edits files with your real credentials. A container bounds the blast radius:

- **Agents ignore instructions.** Even frontier models disregard project and agent rules, for example creating temp files insecurely or running commands you didn't expect. A sandbox is a backstop, not a substitute for trusting the agent to behave.
- **Filesystem scope.** The agent sees only the bind-mounted workspace, not your whole home directory or other projects.
- **Credential exposure is bounded.** Host auth (`~/.gitconfig`, opencode auth/config) is mounted read-only, and only `*_API_KEY`, `GITHUB_TOKEN`, and `GH_TOKEN` are forwarded at exec time (not stored in the container config). Private SSH keys are intentionally not mounted, so the agent cannot read arbitrary host secrets. Run git commands that need credentials (for example push/pull over SSH) on the host. `GITHUB_TOKEN`/`GH_TOKEN` are available inside the container but plain git does not use them for HTTPS auth without a credential helper; run credential-needing git operations on the host.
- **`sudo` without host risk.** Passwordless sudo inside the container maps to your unprivileged host user under rootless podman, not real root.
- **Reversible.** Throw away a bad state with `clankbox rm`; the image is shared and rebuildable.
- **Git hooks and config are protected.** `.git/hooks` is mounted read-only (or replaced with a tmpfs if it does not exist yet), and `.git/config` is mounted read-only when present, so the agent cannot install hooks or set `core.hooksPath` / `core.fsmonitor` / `diff.external` / filter commands that would fire on your next host-side `git commit`, `git checkout`, or `git diff`. Other dangerous files are not protected because the agent needs to edit them as part of normal development. In particular, `.gitattributes` in the workspace is writable and can define `filter.*.smudge` / `clean` commands that execute when you run git on the host. Review changes before running them on the host.
- **Workspace writes are a host escape vector.** The agent can create or modify files in the bind-mounted workspace that later execute on the host outside the sandbox, for example `Makefile`, `.envrc`, `package.json` scripts, and `.github/workflows/*`. Review changes before running them on the host.

## Requirements

- Python 3.10+
- [podman](https://podman.io/)
- network access to build the image and for tools inside the container

## Platforms

Runs on Linux hosts, including Linux guests such as VMs and WSL2 distros (e.g. Ubuntu). On WSL2 or a VM, keep your project on the Linux filesystem (`~/...`) rather than a Windows mount (`/mnt/c/...`) for correct permissions and performance.

## Setting up podman

Install the distro package:

```bash
sudo apt install podman     # Debian / Ubuntu / WSL
sudo dnf install podman     # Fedora
```

Most packages configure rootless mode (subuid/subgid) automatically, so no extra setup is usually needed. Check it works:

```bash
podman run --rm hello-world
```

For other distros see [podman.io](https://podman.io/).

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
clankbox oc              # same, explicitly (alias for 'opencode')
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
clankbox update          # update apt packages, Node.js, and opencode
clankbox update --all    # update all clankbox containers
```

Pass arguments through to opencode:

```bash
clankbox opencode --continue
clankbox oc run "explain this repo"
```

## Design

| Concern | Approach |
|--------|----------|
| Workspace | Current directory bind-mounted at `/workspace` |
| Git hooks/config | `.git/hooks` and `.git/config` mounted read-only (hooks tmpfs if absent) to prevent host-side hook/config injection |
| Identity | One container name per absolute path hash |
| Reuse | Container kept with `sleep infinity`; sessions use `podman exec` |
| Network | Default podman networking (on) |
| Disk | Shared slim image; no named volumes; `rm` drops container layer |
| Host auth | Mounts `~/.local/share/opencode/auth.json`, `~/.config/opencode`, `~/.gitconfig` (read-only) when present |
| API keys | Forwards every `*_API_KEY` env var, plus `GITHUB_TOKEN` / `GH_TOKEN`, at exec time via pass-through (values not in podman args) |
| Resource limits | 512 PIDs, 4g memory (override via `CLANKBOX_PIDS` / `CLANKBOX_MEMORY`) |

Containers are labeled `clankbox=1` so list/rm can find them. The host wrapper is Python 3 (stdlib only).

If you rename or move a project directory, its container name (a path hash) changes, so the old container lingers invisibly. Use `clankbox list` to find and `clankbox rm` to clean it up.

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

Debian bookworm slim plus: git, curl, wget, jq, ripgrep, python3, make/g++, openssh-client, zip/unzip, sudo.

Node.js and opencode are not baked into the image. Each container provisions them on first run (the current LTS Node and latest opencode), so a fresh container is always current without rebuilding the image. The same code path backs `clankbox update`. Because of this, the first run in a new directory takes a little longer while it downloads them; later runs reuse the container and start instantly.

The `clank` user has passwordless `sudo`, so the agent can install extra packages (e.g. `sudo apt install ...`). Under rootless podman this is isolated from host root. Packages persist in that directory's container until `clankbox rm`.
