# Audit

Branch: `audit`.

## Findings (original) and status

1. **Git protections bypassable** — **mitigated (simplified).** Normal `.git`
   directory roots only; modules under `.git/modules` protected; workspace-root
   `.git` file layouts rejected; non-git dirs use tmpfs over `.git`. Residual:
   nested workspace `.git` dirs and submodule pointer files remain writable.
2. **Symlink install exposes launcher** — **mitigated.** Docs use
   `install -m 0755` copy; source tree refused as workspace.
3. **Sensitive workspace paths** — **mitigated.** Denylist.
4. **Rootless not enforced** — **mitigated.**
5. **Mutable upstream install** — **mitigated.** Embedded pins + hashes; no
   `curl | bash`.
6. **Inspect failure + `--replace`** — **mitigated.**
7. **Destructive arg typos** — **mitigated.** Help before Podman.
8. **Update exit/cleanup** — **mitigated.**
9. **Name-only trust** — **mitigated (labels).** Bulk validation; legacy-safe rm.
10. **Query failures as empty** — **mitigated.**
11. **Always `-it`** — **mitigated.**
12. **Persistent credential capture** — **accepted residual.** Documented.

## Design choices after review

- Launcher is self-contained (no `CLANKBOX_ROOT` / `artifacts.json`).
- Git is optional; optimize for normal repo roots and non-git dirs.
- Linked worktrees / submodule checkouts unsupported for in-container Git.
- Tests isolate `XDG_STATE_HOME` under `mktemp -d /tmp/clankbox.XXXXXX`.

## Verification

```bash
python3 -B tests/test_clankbox.py
python3 -B -c 'import ast,pathlib; ast.parse(pathlib.Path("clankbox").read_text())'
```
