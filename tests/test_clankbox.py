#!/usr/bin/env python3
"""Unit tests for clankbox helpers (no real podman required)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_clankbox():
    loader = SourceFileLoader("clankbox_mod", str(ROOT / "clankbox"))
    spec = spec_from_loader(loader.name, loader)
    mod = module_from_spec(spec)
    loader.exec_module(mod)
    return mod


cb = load_clankbox()


class ParseAllFlagTests(unittest.TestCase):
    def test_empty(self):
        self.assertFalse(cb.parse_all_flag([], "rm"))

    def test_all(self):
        self.assertTrue(cb.parse_all_flag(["--all"], "rm"))
        self.assertTrue(cb.parse_all_flag(["-a"], "stop"))

    def test_unknown_raises(self):
        with self.assertRaises(SystemExit) as ctx:
            cb.parse_all_flag(["--help"], "rm")
        self.assertEqual(ctx.exception.code, 0)
        with self.assertRaises(SystemExit) as ctx:
            cb.parse_all_flag(["--al"], "rm")
        self.assertNotEqual(ctx.exception.code, 0)
        with self.assertRaises(SystemExit):
            cb.parse_all_flag(["--all", "extra"], "rm")


class GuardWorkspaceTests(unittest.TestCase):
    def test_rejects_home(self):
        with self.assertRaises(SystemExit):
            cb.guard_workspace(Path.home().resolve())

    def test_rejects_root(self):
        with self.assertRaises(SystemExit):
            cb.guard_workspace(Path("/"))

    def test_rejects_ssh(self):
        path = Path.home().resolve() / ".ssh"
        with self.assertRaises(SystemExit):
            cb.guard_workspace(path)

    def test_rejects_proc(self):
        with self.assertRaises(SystemExit):
            cb.guard_workspace(Path("/proc"))

    def test_rejects_script_dir_tree(self):
        with self.assertRaises(SystemExit):
            cb.guard_workspace(cb.SCRIPT_DIR)

    def test_accepts_temp_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve()
            # Ensure not under sensitive roots.
            cb.guard_workspace(path)


class ContainerStateTests(unittest.TestCase):
    def test_not_found(self):
        def fake_run(args, check=True, capture=False, quiet=False):
            return subprocess.CompletedProcess(
                args, 125, stdout="", stderr="Error: no such container abc"
            )

        with mock.patch.object(cb, "run", side_effect=fake_run):
            self.assertIsNone(cb.container_state("abc"))

    def test_inspect_error_dies(self):
        def fake_run(args, check=True, capture=False, quiet=False):
            return subprocess.CompletedProcess(
                args, 125, stdout="", stderr="cannot connect to podman"
            )

        with mock.patch.object(cb, "run", side_effect=fake_run):
            with self.assertRaises(SystemExit):
                cb.container_state("abc")

    def test_running(self):
        def fake_run(args, check=True, capture=False, quiet=False):
            return subprocess.CompletedProcess(args, 0, stdout="running\n", stderr="")

        with mock.patch.object(cb, "run", side_effect=fake_run):
            self.assertEqual(cb.container_state("abc"), "running")


def _label_run_factory(directory: Path, *, schema: str | None = cb.SCHEMA_VERSION, state: str = "exited"):
    def fake_run(args, check=True, capture=False, quiet=False):
        joined = " ".join(args)
        if "State.Status" in joined:
            return subprocess.CompletedProcess(args, 0, stdout=f"{state}\n", stderr="")
        if f'index .Config.Labels "{cb.LABEL_KEY}"' in joined:
            return subprocess.CompletedProcess(args, 0, stdout="1\n", stderr="")
        if f'index .Config.Labels "{cb.LABEL_WORKDIR}"' in joined:
            return subprocess.CompletedProcess(args, 0, stdout=f"{directory}\n", stderr="")
        if f'index .Config.Labels "{cb.LABEL_SCHEMA}"' in joined:
            value = schema if schema is not None else ""
            return subprocess.CompletedProcess(args, 0, stdout=f"{value}\n", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

    return fake_run


class OwnershipTests(unittest.TestCase):
    def test_mismatch_workdir(self):
        directory = Path("/tmp/project-a")
        name = cb.container_name(directory)

        def fake_run(args, check=True, capture=False, quiet=False):
            joined = " ".join(args)
            if "State.Status" in joined:
                return subprocess.CompletedProcess(args, 0, stdout="running\n", stderr="")
            if f'index .Config.Labels "{cb.LABEL_KEY}"' in joined:
                return subprocess.CompletedProcess(args, 0, stdout="1\n", stderr="")
            if f'index .Config.Labels "{cb.LABEL_WORKDIR}"' in joined:
                return subprocess.CompletedProcess(
                    args, 0, stdout="/tmp/other\n", stderr=""
                )
            if f'index .Config.Labels "{cb.LABEL_SCHEMA}"' in joined:
                return subprocess.CompletedProcess(
                    args, 0, stdout=f"{cb.SCHEMA_VERSION}\n", stderr=""
                )
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

        with mock.patch.object(cb, "run", side_effect=fake_run):
            with self.assertRaises(SystemExit):
                cb.require_owned_container(name, directory)

    def test_ok(self):
        directory = Path("/tmp/project-a")
        name = cb.container_name(directory)
        with mock.patch.object(cb, "run", side_effect=_label_run_factory(directory)):
            self.assertEqual(cb.require_owned_container(name, directory), "exited")

    def test_legacy_schema_blocks_use_but_allows_rm(self):
        directory = Path("/tmp/project-legacy")
        name = cb.container_name(directory)
        with mock.patch.object(
            cb, "run", side_effect=_label_run_factory(directory, schema=None)
        ):
            with self.assertRaises(SystemExit):
                cb.require_owned_container(name, directory)
            self.assertEqual(cb.require_removable_container(name, directory), "exited")


class GitMountTests(unittest.TestCase):
    def test_no_git_uses_tmpfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            args = cb.git_mount_args(directory)
            self.assertIn("type=tmpfs,destination=/workspace/.git", " ".join(args))

    def test_normal_repo_protects_hooks_and_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            git = directory / ".git"
            (git / "hooks").mkdir(parents=True)
            (git / "objects").mkdir()
            (git / "refs").mkdir()
            (git / "HEAD").write_text("ref: refs/heads/main\n")
            (git / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
            (git / "config.worktree").write_text("[core]\n\thooksPath = /tmp/evil\n")
            args = cb.git_mount_args(directory)
            joined = " ".join(args)
            self.assertIn(f"{git / 'hooks'}:/workspace/.git/hooks:ro,z", joined)
            self.assertIn(f"{git / 'config'}:/workspace/.git/config:ro,z", joined)
            self.assertIn(
                f"{git / 'config.worktree'}:/workspace/.git/config.worktree:ro,z",
                joined,
            )
            self.assertNotIn(":ro,Z", joined)

    def test_nested_submodule_gitdir_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            git = directory / ".git"
            nested = git / "modules" / "vendor" / "lib"
            (nested / "hooks").mkdir(parents=True)
            (nested / "objects").mkdir()
            (nested / "refs").mkdir()
            (nested / "HEAD").write_text("ref: refs/heads/main\n")
            (nested / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
            (git / "HEAD").write_text("ref: refs/heads/main\n")
            (git / "objects").mkdir()
            (git / "refs").mkdir()
            (git / "hooks").mkdir()
            (git / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
            args = cb.git_mount_args(directory)
            joined = " ".join(args)
            self.assertIn(
                f"{nested / 'hooks'}:/workspace/.git/modules/vendor/lib/hooks:ro,z",
                joined,
            )
            self.assertIn(
                f"{nested / 'config'}:/workspace/.git/modules/vendor/lib/config:ro,z",
                joined,
            )

    def test_relative_submodule_pointer_uses_generated_gitfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            git = directory / ".git"
            nested = git / "modules" / "lib"
            for path in (nested / "hooks", nested / "objects", nested / "refs"):
                path.mkdir(parents=True)
            (nested / "HEAD").write_text("ref: refs/heads/main\n")
            (nested / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
            (git / "HEAD").write_text("ref: refs/heads/main\n")
            (git / "objects").mkdir()
            (git / "refs").mkdir()
            (git / "hooks").mkdir()
            (git / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
            sub = directory / "vendor" / "lib"
            sub.mkdir(parents=True)
            (sub / ".git").write_text("gitdir: ../../.git/modules/lib\n")
            args = cb.git_mount_args(directory)
            joined = " ".join(args)
            self.assertIn(":/workspace/vendor/lib/.git:ro,z", joined)
            self.assertNotIn(
                f"{sub / '.git'}:/workspace/vendor/lib/.git:ro,z",
                joined,
            )
            self.assertIn(
                f"{nested / 'hooks'}:/workspace/.git/modules/lib/hooks:ro,z",
                joined,
            )

    def test_rejects_arbitrary_external_gitdir_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            git = directory / ".git"
            git.mkdir()
            (git / "HEAD").write_text("ref: refs/heads/main\n")
            (git / "objects").mkdir()
            (git / "refs").mkdir()
            (git / "hooks").mkdir()
            (git / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
            outside = Path(tmp).resolve().parent / f"outside-{os.getpid()}"
            outside.mkdir()
            try:
                (outside / "HEAD").write_text("ref: refs/heads/main\n")
                (outside / "objects").mkdir()
                (outside / "refs").mkdir()
                evil = directory / "nested"
                evil.mkdir()
                (evil / ".git").write_text(f"gitdir: {outside}\n")
                with self.assertRaises(SystemExit):
                    cb.git_mount_args(directory)
            finally:
                shutil.rmtree(outside, ignore_errors=True)

    def test_rejects_symlink_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            target = directory / "elsewhere"
            target.mkdir()
            (directory / ".git").symlink_to(target)
            with self.assertRaises(SystemExit):
                cb.git_mount_args(directory)

    def test_worktree_pointer_mounts_external_gitdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            main = root / "main"
            linked = root / "linked"
            main.mkdir()
            linked.mkdir()
            gitdir = main / ".git" / "worktrees" / "linked"
            gitdir.mkdir(parents=True)
            (gitdir / "HEAD").write_text("ref: refs/heads/main\n")
            (gitdir / "commondir").write_text("../..\n")
            (gitdir / "gitdir").write_text(f"{linked / '.git'}\n")
            (main / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
            (main / ".git" / "objects").mkdir()
            (main / ".git" / "refs").mkdir()
            (main / ".git" / "hooks").mkdir()
            (main / ".git" / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
            (gitdir / "objects").mkdir()
            (gitdir / "refs").mkdir()
            (gitdir / "hooks").mkdir()
            (gitdir / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
            (linked / ".git").write_text(f"gitdir: {gitdir}\n")
            args = cb.git_mount_args(linked)
            joined = " ".join(args)
            self.assertIn(":/workspace/.git:ro,z", joined)
            self.assertNotIn(f"{linked / '.git'}:/workspace/.git:ro,z", joined)
            self.assertIn(f"{gitdir}:{gitdir}:rw,z", joined)
            common = (main / ".git").resolve()
            self.assertIn(f"{common}:{common}:rw,z", joined)


class CreateArgsTests(unittest.TestCase):
    def test_create_has_no_replace_and_has_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            captured: list[list[str]] = []

            def fake_run(args, check=True, capture=False, quiet=False):
                captured.append(list(args))
                return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr="")

            with mock.patch.object(cb, "run", side_effect=fake_run):
                with mock.patch.object(cb, "guard_workspace"):
                    cb.create_container("clankbox-test", directory)
            self.assertTrue(captured)
            args = captured[0]
            self.assertNotIn("--replace", args)
            self.assertIn(f"{cb.LABEL_SCHEMA}={cb.SCHEMA_VERSION}", args)


class CmdRmArgsTests(unittest.TestCase):
    def test_rm_help_does_not_remove(self):
        calls: list[list[str]] = []

        def fake_run(args, check=True, capture=False, quiet=False):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with mock.patch.object(cb, "need_podman", return_value="/usr/bin/podman"):
            with mock.patch.object(cb, "run", side_effect=fake_run):
                with self.assertRaises(SystemExit) as ctx:
                    cb.cmd_rm(["--help"])
                self.assertEqual(ctx.exception.code, 0)
        self.assertEqual(calls, [])

    def test_rm_typo_does_not_remove(self):
        calls: list[list[str]] = []

        def fake_run(args, check=True, capture=False, quiet=False):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with mock.patch.object(cb, "need_podman", return_value="/usr/bin/podman"):
            with mock.patch.object(cb, "run", side_effect=fake_run):
                with self.assertRaises(SystemExit):
                    cb.cmd_rm(["--al"])
        self.assertEqual(calls, [])

    def test_rm_legacy_schema_removes(self):
        directory = Path("/tmp/project-legacy-rm")
        name = cb.container_name(directory)
        calls: list[list[str]] = []

        def fake_run(args, check=True, capture=False, quiet=False):
            calls.append(list(args))
            joined = " ".join(args)
            if args[:2] == ["podman", "rm"]:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            return _label_run_factory(directory, schema=None)(
                args, check=check, capture=capture, quiet=quiet
            )

        with mock.patch.object(cb, "need_podman", return_value="/usr/bin/podman"):
            with mock.patch.object(cb, "workdir", return_value=directory):
                with mock.patch.object(cb, "container_lock") as lock:
                    lock.return_value.__enter__ = lambda s: None
                    lock.return_value.__exit__ = lambda *a: None
                    with mock.patch.object(cb, "run", side_effect=fake_run):
                        cb.cmd_rm([])
        self.assertTrue(any(c[:3] == ["podman", "rm", "-f"] and name in c for c in calls))


class UpdateExitTests(unittest.TestCase):
    def test_update_failure_exits_nonzero(self):
        directory = Path("/tmp/proj")
        name = cb.container_name(directory)

        with mock.patch.object(cb, "need_podman", return_value="/usr/bin/podman"):
            with mock.patch.object(cb, "workdir", return_value=directory):
                with mock.patch.object(cb, "guard_workspace"):
                    with mock.patch.object(cb, "container_lock") as lock:
                        lock.return_value.__enter__ = lambda s: None
                        lock.return_value.__exit__ = lambda *a: None
                        with mock.patch.object(cb, "ensure_running"):
                            with mock.patch.object(cb, "_update_one", return_value=1):
                                with self.assertRaises(SystemExit) as ctx:
                                    cb.cmd_update([])
                                self.assertNotEqual(ctx.exception.code, 0)


class ExecTtyTests(unittest.TestCase):
    def test_no_tty_without_terminals(self):
        captured: list[list[str]] = []

        def fake_execvp(file, args):
            captured.append(list(args))
            raise SystemExit(0)

        with mock.patch.object(cb, "container_has_x11", return_value=False):
            with mock.patch.object(sys.stdin, "isatty", return_value=False):
                with mock.patch.object(sys.stdout, "isatty", return_value=False):
                    with mock.patch.object(os, "execvp", side_effect=fake_execvp):
                        with self.assertRaises(SystemExit):
                            cb.exec_in("ctr", ["bash"])
        self.assertTrue(captured)
        self.assertIn("-i", captured[0])
        self.assertNotIn("-t", captured[0])

    def test_tty_when_interactive(self):
        captured: list[list[str]] = []

        def fake_execvp(file, args):
            captured.append(list(args))
            raise SystemExit(0)

        with mock.patch.object(cb, "container_has_x11", return_value=False):
            with mock.patch.object(sys.stdin, "isatty", return_value=True):
                with mock.patch.object(sys.stdout, "isatty", return_value=True):
                    with mock.patch.object(os, "execvp", side_effect=fake_execvp):
                        with self.assertRaises(SystemExit):
                            cb.exec_in("ctr", ["bash"])
        self.assertIn("-t", captured[0])
        self.assertIn("-i", captured[0])


class ArtifactsTests(unittest.TestCase):
    def test_artifacts_load(self):
        data = cb.load_artifacts()
        self.assertIn("node", data)
        self.assertIn("opencode", data)
        self.assertIn("x64", data["node"]["sha256"])
        self.assertIn("x64-baseline", data["opencode"]["sha256"])
        script = cb.build_provision_script()
        self.assertIn(data["node"]["version"], script)
        self.assertIn(data["opencode"]["version"], script)
        self.assertIn(data["opencode"]["sha256"]["x64-baseline"], script)
        self.assertIn("x64-baseline", script)
        self.assertIn("sha256sum -c", script)
        self.assertIn('trap \'rm -rf "$TMPDIR" "$STAGE"\' EXIT', script)
        self.assertNotIn("opencode.ai/install", script)


if __name__ == "__main__":
    unittest.main()
