# Audit

Branch: `audit` (remediation in progress / applied below).

## Findings

1. **High: Git protections are bypassable.** Writable submodule `.git`
   pointers, nested submodules, and `.git/config.worktree` can allow host-side
   Git to execute injected hooks or configuration. Linked worktrees also break
   because their referenced gitdir is not mounted. See `clankbox:373-407` and
   `SECURITY.md:11`.
   **Status: mitigated.** Recursive module gitdir protection, config.worktree,
   generated absolute pointers for relative gitfiles, external mount allowlist
   (modules/worktrees only), linked worktree backlink checks, and symlink refusal.
   Residual: newly created nested repos during a live session; writable
   objects/refs by design (agents may commit).
2. **High: The recommended symlink installation exposes the host launcher.**
   When this repository is sandboxed, an agent can modify `clankbox`; the next
   host invocation executes it. See `README.md:46-52`.
   **Status: mitigated.** Install docs use `install -m 0755` copy; launcher refuses
   to sandbox its own source tree.
3. **High: Workspace validation permits sensitive directories.**
   `guard_workspace()` permits paths such as `~/.ssh`, `/proc`, and
   `/run/user/$UID`. Mounting the latter may expose the Podman socket and defeat
   isolation. See `clankbox:102-122`.
   **Status: mitigated.** Sensitive-path denylist for credential, runtime, and
   pseudo-filesystem roots.
4. **High: Rootless Podman is assumed but never enforced.** Running through
   root or a rootful connection invalidates the documented security boundary.
   See `clankbox:74-78`, `README.md:13`, and `SECURITY.md:10`.
   **Status: mitigated.** Refuses EUID 0 and requires `podman info` rootless=true.
5. **High: Provisioning executes mutable upstream content.** This includes
   `curl https://opencode.ai/install | bash`. Node checksums come from the
   artifact origin, and NVIDIA's keyring package is unverified. See
   `clankbox:949-980` and `clankbox:1023-1030`.
   **Status: mitigated.** `artifacts.json` pins versions and SHA-256 hashes for
   Node, opencode, and NVIDIA keyring; base image digest-pinned in Dockerfile.
6. **High: An inspect failure can destroy existing container state.** Any
   `podman inspect` failure is treated as "container absent"; `init` then uses
   `create --replace`, potentially deleting the existing writable layer. See
   `clankbox:177-186` and `clankbox:309-313`.
   **Status: mitigated.** Not-found vs error distinguished; `--replace` removed.
7. **High: Invalid destructive arguments are accepted.** For example,
   `clankbox rm --help` removes the current container, while
   `clankbox rm --all extra` removes all containers. See `clankbox:845-902`.
   **Status: mitigated.** Strict `--all`/`-a` parsing; unknown args fail closed.
8. **Medium: Update failures return success and cleanup is incomplete.** A
   failed update prints an error but exits successfully. `update --all` can
   also leave initially stopped containers running after interruption. See
   `clankbox:1090-1168`.
   **Status: mitigated.** Nonzero exit on failure; `finally` restores stopped
   containers after `update --all`.
9. **Medium: Containers are trusted solely by predictable name.** Labels,
   workdir, image, mounts, user namespace, and network mode are not validated
   before execution or deletion. See `clankbox:125-127` and
   `clankbox:573-589`.
   **Status: mitigated (labels).** Requires `clankbox=1`, workdir match, and
   name/hash consistency. Current schema required for use; removal allows legacy
   schemas. Bulk commands validate each target. Full mount/image fingerprinting
   not implemented.
10. **Medium: Failed Podman queries are reported as empty results.** This masks
    service and permission errors. See `clankbox:709-727`, `clankbox:767-798`,
    and `clankbox:849-885`.
    **Status: mitigated.** Query failures die with stderr detail.
11. **Medium: Every execution requests an interactive TTY.** Using
    `podman exec -it` unconditionally makes redirected and CI usage unreliable.
    See `clankbox:685-706`.
    **Status: mitigated.** `-t` only when stdin and stdout are TTYs.
12. **Medium: Persistent containers can capture future credentials.** A
    container with passwordless sudo can replace tooling and capture
    credentials forwarded during later sessions. See `clankbox:543-555` and
    `clankbox:702-705`.
    **Status: accepted residual.** Documented; recreate containers across trust
    or credential boundaries.

## Test Gaps

Addressed with `tests/test_clankbox.py` (CLI parsing, inspect errors, ownership,
legacy removal, Git layouts including relative pointers and rejected external
gitdirs, update exit status, TTY flags, artifacts loading including baseline).
Remaining: integration tests against real rootless podman that prove commit
works while hooks stay immutable; interrupt-path coverage for `update --all`.

## Remediation Order

1. Remove `--replace`, distinguish not-found from Podman failures, and validate
   container identity. **Done**
2. Add strict argument parsing and correct failure exit codes. **Done**
3. Redesign Git metadata isolation (commit-capable). **Done (best-effort)**
4. Enforce rootless operation and strengthen workspace validation and install
   guidance. **Done**
5. Pin and verify downloaded artifacts, then add automated tests. **Done**

## Verification

```bash
python3 -B tests/test_clankbox.py
python3 -B -c 'import ast,pathlib; ast.parse(pathlib.Path("clankbox").read_text())'
```
