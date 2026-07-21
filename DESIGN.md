# Design

| Concern | Approach |
|--------|----------|
| Workspace | Current directory bind-mounted at `/workspace`; sensitive host paths rejected; Git optional |
| Git hooks/config | Only normal `.git` directories at the workspace root; hooks/config/attributes and `.git/modules` admin paths read-only; index/objects/refs writable for commits; workspace-root `.git` file layouts unsupported; nested submodule pointer files not specially mounted; non-git dirs get tmpfs over `/workspace/.git` |
| Identity | One container name per absolute path hash; labels `clankbox=1` and workdir validated; current schema required except for removal |
| Reuse | Container kept with `sleep infinity`; sessions use `podman exec` |
| Network | Default podman networking (on) |
| Disk | Shared slim image; no named volumes; `rm` drops container layer |
| Host auth | Mounts `~/.local/share/opencode/auth.json`, `~/.config/opencode`, `~/.gitconfig` (read-only) when present; auth copied into writable container storage on start |
| API keys | Forwards every `*_API_KEY` env var, plus `GITHUB_TOKEN` / `GH_TOKEN`, at exec time |
| Resource limits | 512 PIDs, 4g memory (override via `CLANKBOX_PIDS` / `CLANKBOX_MEMORY`) |
| GPU (optional) | `init --nvidia`: CDI device `nvidia.com/gpu=all`; CUDA runtime libs provisioned; label `clankbox.nvidia=1` |
| X11 (optional) | `init --x11`: `--network=host`; display sockets; `XAUTHORITY` synced; label `clankbox.x11=1` |
| Tool versions | Pinned in launcher `ARTIFACTS` with SHA-256 hashes; base image digest embedded; Dockerfile also kept in-repo as a readable mirror |
| Engine | Rootless podman required |
| Distribution | Single self-contained launcher binary; reinstall copy after pull |

If you rename or move a project directory, its container name changes. Use
`clankbox list`, then `cd` to the old path and `clankbox rm`, or `clankbox rm --all`,
or `podman rm -f NAME`.

Schema bumps require `clankbox rm` then `clankbox init`. Removal accepts legacy schemas.
