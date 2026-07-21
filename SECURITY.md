# Security details

Clankbox reduces risk but does not eliminate it. Below is a fuller account of what is protected, what is not, and the residual risks.

## What the sandbox limits

- **Filesystem scope.** The agent sees the bind-mounted workspace plus any validated Git admin directories required for worktrees/submodules. It does not get a general view of your home directory or other projects. The launcher refuses sensitive roots such as `~/.ssh`, `~/.gnupg`, XDG runtime/state/config/data trees, `/proc`, `/sys`, `/dev`, `/run`, and the clankbox source tree itself.
- **Host auth mounted read-only, then copied.** `~/.gitconfig`, `~/.config/opencode`, and `~/.local/share/opencode/auth.json` are mounted read-only when present. `auth.json` is also copied into writable container storage on start so opencode can refresh tokens inside the sandbox. Private SSH keys are intentionally not mounted.
- **API key forwarding.** Only `*_API_KEY`, `GITHUB_TOKEN`, and `GH_TOKEN` are forwarded at exec time via pass-through (values are not stored in the container config or podman args). `GITHUB_TOKEN`/`GH_TOKEN` are available inside the container but plain git does not use them for HTTPS auth without a credential helper; run credential-needing git operations on the host.
- **`sudo` without host-root privileges.** Passwordless sudo inside the container maps to your unprivileged host user under rootless podman, not real root. Clankbox refuses to run as host root and requires rootless podman.
- **Git hooks and config.** Shared Git metadata stays writable for index, objects, refs, and logs so agents can stage and commit. Executable configuration is overlaid read-only: `hooks`, `config`, `config.worktree`, `info/attributes`, nested submodule gitdirs under `.git/modules`, workspace-side submodule `.git` pointer files (rewritten to generated absolute pointers), and linked-worktree gitdir/commondir admin paths. Only module/worktree metadata paths are eligible for external mounts; arbitrary host repositories are refused. Missing hooks directories use tmpfs placeholders; missing config/attributes use empty read-only placeholders. Symlinked `.git` paths are refused.
- **Container identity.** Single-container commands require label `clankbox=1`, an exact workdir label match, and a name that hashes to that workdir. Start/exec/stop/update also require the current schema version. Removal allows legacy schemas so migration stays possible. Bulk commands validate each selected container the same way (`rm --all` allows legacy schemas; `stop --all` / `update --all` require the current schema).
- **Pinned downloads.** Node.js, opencode (including x64-baseline), and the NVIDIA keyring package are verified against SHA-256 hashes in `artifacts.json`. The Debian base image is digest-pinned. Apt package upgrades inside the container are not fully pinned.

## What the sandbox does not stop

- **Agents ignore instructions.** Even frontier models disregard project and agent rules, for example creating temp files insecurely or running commands you didn't expect. A sandbox is a backstop, not a substitute for trusting the agent to behave.
- **Credential exfiltration.** The mounted `auth.json` contains every opencode provider credential (API keys and OAuth tokens), and network is enabled inside the container, so the agent can read and exfiltrate them. If this is unacceptable, avoid running clankbox with untrusted agents or remove `auth.json` before starting.
- **Persistent container credential reuse.** The reusable container has passwordless sudo and a writable rootfs. A compromised session can replace tooling and capture credentials forwarded in later sessions. Treat a container as untrusted after any suspect session; run `clankbox rm` before introducing new credentials or raising trust. Removing host `auth.json` does not scrub copies already inside an existing container layer.
- **Token refresh drift.** On each start, `auth.json` is re-copied from the host into the container, overwriting any token refresh that happened inside the container; if a provider rotates refresh tokens, the host copy may become stale, so re-authenticate on the host if opencode reports invalid credentials.
- **Git credentials over SSH.** Private SSH keys are not mounted. Run git commands that need credentials (for example push/pull over SSH) on the host.
- **Workspace writes are a host escape vector.** The agent can create or modify files in the bind-mounted workspace that later execute on the host outside the sandbox, for example `Makefile`, `.envrc`, `package.json` scripts, and `.github/workflows/*`. Review changes before running them on the host.
- **Git residual risk.** Index, objects, refs, and commit contents remain agent-writable by design. Newly created nested repositories or submodule metadata during a live session are not retroactively protected by static bind mounts until the container is recreated. Host Git config may still define filter drivers that a workspace `.gitattributes` can select; review those files before host-side Git operations.
- **X11 display access.** With `init --x11`, the container can connect to the host X server (windows, input, screenshots) and shares the host network namespace (`--network=host`) so SSH `-Y` localhost proxies work. Only enable when you need graphical apps inside the sandbox.
- **Installer location.** Install a copied launcher outside sandboxed workspaces. Do not symlink `clankbox` into a project directory you open with clankbox.

## Install hygiene

```bash
install -m 0755 ./clankbox ~/.local/bin/clankbox
export CLANKBOX_ROOT=~/src/clankbox   # dedicated checkout, not a workspace
```

Prefer a dedicated clone path that is never used as a clankbox workspace.
