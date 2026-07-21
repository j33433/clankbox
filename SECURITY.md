# Security details

Clankbox reduces risk but does not eliminate it.

## What the sandbox limits

- **Filesystem scope.** The agent sees the bind-mounted workspace. Sensitive roots such as `~/.ssh`, `~/.gnupg`, XDG runtime/state/config/data trees, `/proc`, `/sys`, `/dev`, `/run`, and the clankbox source tree are refused.
- **Host auth mounted read-only, then copied.** `~/.gitconfig`, `~/.config/opencode`, and `~/.local/share/opencode/auth.json` are mounted read-only when present. `auth.json` is copied into writable container storage on start so tokens can refresh. Private SSH keys are not mounted.
- **API key forwarding.** Only `*_API_KEY`, `GITHUB_TOKEN`, and `GH_TOKEN` are forwarded at exec time.
- **`sudo` without host-root privileges.** Passwordless sudo maps to your unprivileged host user under rootless podman. Host root and rootful podman are refused.
- **Git hooks and config (optional Git).** When the workspace root has a normal `.git` directory, hooks, `config`, `config.worktree`, `info/attributes`, and module admin paths under `.git/modules` are overlaid read-only. Index, objects, refs, and logs stay writable for commits. Non-git workspaces get a tmpfs over `/workspace/.git` so the agent cannot create host-visible Git metadata. Linked worktrees and submodule checkouts (`.git` file) are rejected with a clear error rather than partially mounted.
- **Container identity.** Single-container commands require `clankbox=1`, workdir match, and name/hash consistency. Start/exec/stop/update require the current schema. Removal allows legacy schemas. Bulk commands validate each target.
- **Pinned downloads.** Node.js, opencode (including x64-baseline), and the NVIDIA keyring package are verified against embedded SHA-256 hashes. The Debian base image is digest-pinned. Apt upgrades are not fully pinned.

## What the sandbox does not stop

- **Agents ignore instructions.**
- **Credential exfiltration** over the network from mounted/copied auth and forwarded env vars.
- **Persistent container credential reuse.** Recreate with `clankbox rm` across trust boundaries.
- **Token refresh drift** if host and container auth copies diverge.
- **Git credentials over SSH.** Private keys are not mounted.
- **Workspace writes** that later execute on the host (`Makefile`, CI configs, etc.).
- **Git residual risk.** Commits and object stores remain agent-writable by design. Read-only config means in-container `git config` / remote edits fail; do those on the host when needed. Nested independent `.git` directories inside the workspace are not recursively protected beyond the primary repo modules tree.
- **X11** with `init --x11` (display access and host networking).
- **Installer location.** Install a copied launcher outside sandboxed workspaces.

## Install hygiene

```bash
mkdir -p ~/.local/bin
install -m 0755 ./clankbox ~/.local/bin/clankbox
```

After updating the checkout, reinstall the copy so pins and code stay matched.
