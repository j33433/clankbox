# clankbox

![clankbox logo](logo/logo.png)

A container for safer vibecoding. Runs [opencode](https://opencode.ai) in a reusable podman container bound to your current directory.

## Why run opencode in a container?

An autonomous agent runs shell commands and edits files with your real credentials. A container bounds the blast radius:

- **Filesystem scope.** The agent sees only the bind-mounted workspace, not your whole home directory or other projects. Sensitive host paths (for example `~/.ssh`, `/proc`, runtime dirs) are rejected.
- **Credential exposure is bounded.** Host auth is mounted read-only, private SSH keys are not mounted, and only specific API key env vars are forwarded at exec time. Network is enabled, so the agent can still exfiltrate what it can read.
- **`sudo` without host-root privileges.** Passwordless sudo inside the container maps to your unprivileged host user under rootless podman, not real root. Rootful podman is refused.
- **Git hooks and config are protected.** Executable Git metadata (hooks, config, worktree config, attributes, submodule metadata) is mounted read-only so the agent cannot install host-side hooks. Index, objects, and refs stay writable so the agent can stage and commit. Linked worktree/module admin dirs outside the workspace may be mounted when required for Git to function.
- **Reversible.** Throw away a bad state with `clankbox rm`; the image is shared and rebuildable.
- **Pinned tools.** Node.js, opencode archives, and the NVIDIA keyring package use versions and SHA-256 hashes from `artifacts.json`. Apt package upgrades inside the container remain rolling.

A sandbox is a backstop, not a substitute for judgment. Agents ignore instructions, and workspace writes (Makefiles, scripts, CI configs) can execute on the host outside the container. Review changes before running them on the host. See [Security details](SECURITY.md) for the full picture.

## Requirements

- Python 3.10+
- [podman](https://podman.io/) in **rootless** mode
- network access to build the image and for tools inside the container
- Linux amd64 or arm64 (Node and opencode pins cover these architectures)

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
podman info --format '{{.Host.Security.Rootless}}'   # should print true
```

For other distros see [podman.io](https://podman.io/).

## Install

Keep a dedicated checkout you will not open as a clankbox workspace (for example
`~/src/clankbox`). Copy the launcher onto your `PATH` and point it at that
checkout when the binary does not sit beside `Dockerfile` / `artifacts.json`:

```bash
# from the dedicated checkout
mkdir -p ~/.local/bin
install -m 0755 ./clankbox ~/.local/bin/clankbox
# ensure ~/.local/bin is on PATH, then:
echo 'export CLANKBOX_ROOT=$HOME/src/clankbox' >> ~/.bashrc   # adjust path
```

After `git pull` in the checkout, re-run the `install` line so the copied launcher stays in sync.

If you run `./clankbox` directly from the checkout, `CLANKBOX_ROOT` is optional.
Do not symlink the launcher into a project directory you will sandbox.

## Usage

```bash
cd /path/to/your/project
clankbox init              # create and provision the container (once per project)
clankbox init --nvidia     # same, plus GPU access and CUDA runtime libraries
clankbox init --x11        # same, plus host X11 display passthrough
clankbox opencode          # start opencode
clankbox oc                # same (alias for 'opencode')
```

`init` builds the image if needed, creates the container, and installs the pinned
Node.js and opencode versions from `artifacts.json`. Other commands require an
initialized container and will tell you to run `clankbox init` if one does not
exist.

Containers created before schema version 2 must be removed and re-created
(`clankbox rm` then `clankbox init`).

`init --nvidia` adds CDI GPU access (`--device nvidia.com/gpu=all`) and installs
NVIDIA CUDA runtime libraries inside the container (not the full toolkit). The
host needs an NVIDIA driver and [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html)
with CDI. To enable GPU on an existing container: `clankbox rm` then
`clankbox init --nvidia`.

`init --x11` forwards the host display into the container: mounts `/tmp/.X11-unix`
when present, mounts `/mnt/wslg` on WSL2/WSLg, copies `XAUTHORITY` cookies each
session, and uses `--network=host` so SSH X11 forwarding (`ssh -Y`,
`DISPLAY=localhost:N`) reaches the host sshd proxy. It installs basic X11
client libraries. Requires a working host `DISPLAY` (local X/WSLg or an
`ssh -Y` session). Host networking is a deliberate tradeoff for X11 only.
Flags can be combined (`init --nvidia --x11`). To enable or refresh X11 on an
existing container: `clankbox rm` then `clankbox init --x11`.

From another terminal in the same project directory:

```bash
clankbox oc                # joins the same container
clankbox shell             # bash in the same container
```

Manage containers:

```bash
clankbox list              # all clankbox containers
clankbox df                # disk space used by sandboxes
clankbox stop              # stop this directory's container
clankbox stop --all
clankbox rm                # remove this directory's container
clankbox rm --all          # remove every clankbox container
clankbox build             # rebuild the image
clankbox update            # update apt packages and re-apply pinned tools
clankbox update --all      # update all clankbox containers
```

Pass arguments through to opencode:

```bash
clankbox opencode --continue
clankbox oc run "explain this repo"
```

## Concurrent terminals

Clankbox uses advisory locks in `~/.local/state/clankbox/locks` (or
`$XDG_STATE_HOME/clankbox/locks`) to serialize image builds and container
lifecycle operations. Starting sessions from multiple terminals in the same
workspace is safe: only one can start or change its shared container.

The locks are released before `podman exec`, so sessions can run concurrently.
They do not coordinate changes inside the shared workspace or container home;
agents can still conflict when editing files, running Git commands, or changing
dependencies. `stop` and `rm` remain destructive commands and can end active
sessions by design.

## Image contents

Debian bookworm slim (digest-pinned) plus: git, curl, wget, jq, ripgrep, python3, make/g++, openssh-client, zip/unzip, sudo.

Node.js and opencode are not baked into the image. `clankbox init` provisions the
pinned versions from `artifacts.json` into each container. The same code path
backs `clankbox update`. Bump pins by editing `artifacts.json` after reviewing
upstream release hashes.

The `clank` user has passwordless `sudo`, so the agent can install extra packages (e.g. `sudo apt install ...`). Under rootless podman this is isolated from host root. Packages persist in that directory's container until `clankbox rm`.

## Tests

```bash
python3 -B tests/test_clankbox.py
```

See [Design](DESIGN.md) for the architecture table and [Security details](SECURITY.md) for residual risk.
