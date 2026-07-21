# Security details

Clankbox reduces risk but does not eliminate it. Below is a fuller account of what is protected, what is not, and the residual risks.

## What the sandbox limits

- **Filesystem scope.** The agent sees only the bind-mounted workspace, not your whole home directory or other projects.
- **Host auth mounted read-only.** `~/.gitconfig`, `~/.config/opencode`, and `~/.local/share/opencode/auth.json` are mounted read-only when present, so the agent cannot modify them. Private SSH keys are intentionally not mounted, so the agent cannot read arbitrary host secrets.
- **API key forwarding.** Only `*_API_KEY`, `GITHUB_TOKEN`, and `GH_TOKEN` are forwarded at exec time via pass-through (values are not stored in the container config or podman args). `GITHUB_TOKEN`/`GH_TOKEN` are available inside the container but plain git does not use them for HTTPS auth without a credential helper; run credential-needing git operations on the host.
- **`sudo` without host risk.** Passwordless sudo inside the container maps to your unprivileged host user under rootless podman, not real root.
- **Git hooks and config.** `.git/hooks` is mounted read-only (or replaced with a tmpfs if it does not exist yet), and `.git/config` is mounted read-only when present, so the agent cannot install hooks or set `core.hooksPath` / `core.fsmonitor` / `diff.external` / filter commands that would fire on your next host-side `git commit`, `git checkout`, or `git diff`. If the workspace is not yet a git repo, a tmpfs is mounted over `.git` so the agent cannot create one with malicious hooks. In a worktree, the `.git` pointer file is mounted read-only so it cannot be repointed at a malicious gitdir. Submodule hooks and config (`.git/modules/*/hooks`, `.git/modules/*/config`) and `.git/info/attributes` are also protected.

## What the sandbox does not stop

- **Agents ignore instructions.** Even frontier models disregard project and agent rules, for example creating temp files insecurely or running commands you didn't expect. A sandbox is a backstop, not a substitute for trusting the agent to behave.
- **Credential exfiltration.** The mounted `auth.json` contains every opencode provider credential (API keys and OAuth tokens), and network is enabled inside the container, so the agent can read and exfiltrate them. If this is unacceptable, avoid running clankbox with untrusted agents or remove `auth.json` before starting.
- **Token refresh drift.** On each start, `auth.json` is re-copied from the host into the container, overwriting any token refresh that happened inside the container; if a provider rotates refresh tokens, the host copy may become stale, so re-authenticate on the host if opencode reports invalid credentials.
- **Git credentials over SSH.** Private SSH keys are not mounted. Run git commands that need credentials (for example push/pull over SSH) on the host.
- **Workspace writes are a host escape vector.** The agent can create or modify files in the bind-mounted workspace that later execute on the host outside the sandbox, for example `Makefile`, `.envrc`, `package.json` scripts, and `.github/workflows/*`. Review changes before running them on the host.
- **X11 display access.** With `init --x11`, the container can connect to the host X server (windows, input, screenshots) and shares the host network namespace (`--network=host`) so SSH `-Y` localhost proxies work. Only enable when you need graphical apps inside the sandbox.
- **`.gitattributes` is writable.** It can define `filter.*.smudge` / `clean` commands that execute when you run git on the host. Other dangerous git files are not protected because the agent needs to edit them as part of normal development. Review changes before running them on the host.
