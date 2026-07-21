# Design

| Concern | Approach |
|--------|----------|
| Workspace | Current directory bind-mounted at `/workspace` |
| Git hooks/config | `.git/hooks`, `.git/config`, submodule hooks/config, and `.git/info/attributes` mounted read-only; tmpfs over `.git` when no repo exists; `.git` pointer file read-only in worktrees |
| Identity | One container name per absolute path hash |
| Reuse | Container kept with `sleep infinity`; sessions use `podman exec` |
| Network | Default podman networking (on) |
| Disk | Shared slim image; no named volumes; `rm` drops container layer |
| Host auth | Mounts `~/.local/share/opencode/auth.json`, `~/.config/opencode`, `~/.gitconfig` (read-only) when present |
| API keys | Forwards every `*_API_KEY` env var, plus `GITHUB_TOKEN` / `GH_TOKEN`, at exec time via pass-through (values not in podman args) |
| Resource limits | 512 PIDs, 4g memory (override via `CLANKBOX_PIDS` / `CLANKBOX_MEMORY`) |
| GPU (optional) | `init --nvidia`: CDI device `nvidia.com/gpu=all` at create time; CUDA runtime libs provisioned in-container; label `clankbox.nvidia=1` |
| X11 (optional) | `init --x11`: `--network=host`; `/tmp/.X11-unix` (+ `/mnt/wslg` on WSLg); `DISPLAY` forwarded and `XAUTHORITY` synced each session; basic X11 libs; label `clankbox.x11=1` |

Containers are labeled `clankbox=1` so list/rm can find them. The host wrapper is Python 3 (stdlib only).

If you rename or move a project directory, its container name (a path hash) changes, so the old container lingers invisibly. Use `clankbox list` to find and `clankbox rm` to clean it up.
