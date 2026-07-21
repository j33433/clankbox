# Design

| Concern | Approach |
|--------|----------|
| Workspace | Current directory bind-mounted at `/workspace`; sensitive host paths rejected |
| Git hooks/config | Shared metadata so agents can stage/commit; hooks, `config`, `config.worktree`, attributes, and submodule/worktree admin paths mounted read-only (recursive); generated absolute gitfiles for relative pointers; external mounts limited to module/worktree metadata; tmpfs over `.git` when no repo exists |
| Identity | One container name per absolute path hash; labels `clankbox=1` and workdir validated before use; current schema required except for removal |
| Reuse | Container kept with `sleep infinity`; sessions use `podman exec` |
| Network | Default podman networking (on) |
| Disk | Shared slim image; no named volumes; `rm` drops container layer |
| Host auth | Mounts `~/.local/share/opencode/auth.json`, `~/.config/opencode`, `~/.gitconfig` (read-only) when present |
| API keys | Forwards every `*_API_KEY` env var, plus `GITHUB_TOKEN` / `GH_TOKEN`, at exec time via pass-through (values not in podman args) |
| Resource limits | 512 PIDs, 4g memory (override via `CLANKBOX_PIDS` / `CLANKBOX_MEMORY`) |
| GPU (optional) | `init --nvidia`: CDI device `nvidia.com/gpu=all` at create time; CUDA runtime libs provisioned in-container; label `clankbox.nvidia=1` |
| X11 (optional) | `init --x11`: `--network=host`; `/tmp/.X11-unix` (+ `/mnt/wslg` on WSLg); `DISPLAY` forwarded and `XAUTHORITY` synced each session; basic X11 libs; label `clankbox.x11=1` |
| Tool versions | Pinned in `artifacts.json` with SHA-256 hashes; base image digest-pinned in `Dockerfile` |
| Engine | Rootless podman required |

Containers are labeled `clankbox=1` so list/rm can find them. The host wrapper is Python 3 (stdlib only).

If you rename or move a project directory, its container name (a path hash) changes, so the old container lingers. Use `clankbox list` to find it, then either `cd` back to the old path and run `clankbox rm`, run `clankbox rm --all`, or `podman rm -f NAME`.

Schema version bumps (label `clankbox.schema`) require removal then `clankbox init`. `clankbox rm` accepts legacy schemas so that migration path works.
