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


def load_clankbox(state_home: Path):
    os.environ["XDG_STATE_HOME"] = str(state_home)
    loader = SourceFileLoader("clankbox_mod", str(ROOT / "clankbox"))
    spec = spec_from_loader(loader.name, loader)
    mod = module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class ClankboxTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="clankbox.", dir="/tmp")
        os.chmod(self._tmpdir, 0o700)
        self.state_home = Path(self._tmpdir) / "state"
        self.state_home.mkdir(mode=0o700)
        self.cb = load_clankbox(self.state_home)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)


class ParseAllFlagTests(ClankboxTestCase):
    def test_empty(self):
        self.assertFalse(self.cb.parse_all_flag([], "rm"))

    def test_all(self):
        self.assertTrue(self.cb.parse_all_flag(["--all"], "rm"))
        self.assertTrue(self.cb.parse_all_flag(["-a"], "stop"))

    def test_unknown_raises(self):
        with self.assertRaises(SystemExit) as ctx:
            self.cb.parse_all_flag(["--help"], "rm")
        self.assertEqual(ctx.exception.code, 0)
        with self.assertRaises(SystemExit) as ctx:
            self.cb.parse_all_flag(["--al"], "rm")
        self.assertNotEqual(ctx.exception.code, 0)
        with self.assertRaises(SystemExit):
            self.cb.parse_all_flag(["--all", "extra"], "rm")


class GuardWorkspaceTests(ClankboxTestCase):
    def test_rejects_home(self):
        with self.assertRaises(SystemExit):
            self.cb.guard_workspace(Path.home().resolve())

    def test_rejects_root(self):
        with self.assertRaises(SystemExit):
            self.cb.guard_workspace(Path("/"))

    def test_rejects_ssh(self):
        with self.assertRaises(SystemExit):
            self.cb.guard_workspace(Path.home().resolve() / ".ssh")

    def test_rejects_proc(self):
        with self.assertRaises(SystemExit):
            self.cb.guard_workspace(Path("/proc"))

    def test_rejects_script_dir_tree(self):
        with self.assertRaises(SystemExit):
            self.cb.guard_workspace(self.cb.SCRIPT_DIR)

    def test_accepts_temp_project(self):
        with tempfile.TemporaryDirectory(prefix="clankbox.", dir="/tmp") as tmp:
            self.cb.guard_workspace(Path(tmp).resolve())


class ContainerStateTests(ClankboxTestCase):
    def test_not_found(self):
        def fake_run(args, check=True, capture=False, quiet=False):
            return subprocess.CompletedProcess(
                args, 125, stdout="", stderr="Error: no such container abc"
            )

        with mock.patch.object(self.cb, "run", side_effect=fake_run):
            self.assertIsNone(self.cb.container_state("abc"))

    def test_inspect_error_dies(self):
        def fake_run(args, check=True, capture=False, quiet=False):
            return subprocess.CompletedProcess(
                args, 125, stdout="", stderr="cannot connect to podman"
            )

        with mock.patch.object(self.cb, "run", side_effect=fake_run):
            with self.assertRaises(SystemExit):
                self.cb.container_state("abc")

    def test_running(self):
        def fake_run(args, check=True, capture=False, quiet=False):
            return subprocess.CompletedProcess(args, 0, stdout="running\n", stderr="")

        with mock.patch.object(self.cb, "run", side_effect=fake_run):
            self.assertEqual(self.cb.container_state("abc"), "running")


def _label_run_factory(cb, directory: Path, *, schema: str | None = None, state: str = "exited"):
    if schema is None:
        schema = cb.SCHEMA_VERSION

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


class OwnershipTests(ClankboxTestCase):
    def test_mismatch_workdir(self):
        directory = Path("/tmp/project-a")
        name = self.cb.container_name(directory)

        def fake_run(args, check=True, capture=False, quiet=False):
            joined = " ".join(args)
            if "State.Status" in joined:
                return subprocess.CompletedProcess(args, 0, stdout="running\n", stderr="")
            if f'index .Config.Labels "{self.cb.LABEL_KEY}"' in joined:
                return subprocess.CompletedProcess(args, 0, stdout="1\n", stderr="")
            if f'index .Config.Labels "{self.cb.LABEL_WORKDIR}"' in joined:
                return subprocess.CompletedProcess(
                    args, 0, stdout="/tmp/other\n", stderr=""
                )
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

        with mock.patch.object(self.cb, "run", side_effect=fake_run):
            with self.assertRaises(SystemExit):
                self.cb.require_owned_container(name, directory)

    def test_ok(self):
        directory = Path("/tmp/project-a")
        name = self.cb.container_name(directory)
        with mock.patch.object(
            self.cb, "run", side_effect=_label_run_factory(self.cb, directory)
        ):
            self.assertEqual(self.cb.require_owned_container(name, directory), "exited")

    def test_legacy_schema_blocks_use_but_allows_rm(self):
        directory = Path("/tmp/project-legacy")
        name = self.cb.container_name(directory)
        with mock.patch.object(
            self.cb,
            "run",
            side_effect=_label_run_factory(self.cb, directory, schema="2"),
        ):
            with self.assertRaises(SystemExit):
                self.cb.require_owned_container(name, directory)
            self.assertEqual(
                self.cb.require_removable_container(name, directory), "exited"
            )


class GitMountTests(ClankboxTestCase):
    def test_no_git_uses_tmpfs(self):
        with tempfile.TemporaryDirectory(prefix="clankbox.", dir="/tmp") as tmp:
            directory = Path(tmp).resolve()
            args = self.cb.git_mount_args(directory)
            self.assertIn("type=tmpfs,destination=/workspace/.git", " ".join(args))

    def test_normal_repo_protects_hooks_and_config(self):
        with tempfile.TemporaryDirectory(prefix="clankbox.", dir="/tmp") as tmp:
            directory = Path(tmp).resolve()
            git = directory / ".git"
            (git / "hooks").mkdir(parents=True)
            (git / "objects").mkdir()
            (git / "refs").mkdir()
            (git / "HEAD").write_text("ref: refs/heads/main\n")
            (git / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
            (git / "config.worktree").write_text("[core]\n\thooksPath = /tmp/evil\n")
            args = self.cb.git_mount_args(directory)
            joined = " ".join(args)
            self.assertIn(f"{git / 'hooks'}:/workspace/.git/hooks:ro,z", joined)
            self.assertIn(f"{git / 'config'}:/workspace/.git/config:ro,z", joined)
            self.assertIn(
                f"{git / 'config.worktree'}:/workspace/.git/config.worktree:ro,z",
                joined,
            )

    def test_nested_module_config_protected(self):
        with tempfile.TemporaryDirectory(prefix="clankbox.", dir="/tmp") as tmp:
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
            args = self.cb.git_mount_args(directory)
            joined = " ".join(args)
            self.assertIn(
                f"{nested / 'hooks'}:/workspace/.git/modules/vendor/lib/hooks:ro,z",
                joined,
            )
            self.assertIn(
                f"{nested / 'config'}:/workspace/.git/modules/vendor/lib/config:ro,z",
                joined,
            )

    def test_rejects_gitfile_workspace(self):
        with tempfile.TemporaryDirectory(prefix="clankbox.", dir="/tmp") as tmp:
            directory = Path(tmp).resolve()
            (directory / ".git").write_text("gitdir: /somewhere/else\n")
            with self.assertRaises(SystemExit):
                self.cb.git_mount_args(directory)

    def test_rejects_symlink_git(self):
        with tempfile.TemporaryDirectory(prefix="clankbox.", dir="/tmp") as tmp:
            directory = Path(tmp).resolve()
            target = directory / "elsewhere"
            target.mkdir()
            (directory / ".git").symlink_to(target)
            with self.assertRaises(SystemExit):
                self.cb.git_mount_args(directory)


class CreateArgsTests(ClankboxTestCase):
    def test_create_has_no_replace_and_has_schema(self):
        with tempfile.TemporaryDirectory(prefix="clankbox.", dir="/tmp") as tmp:
            directory = Path(tmp).resolve()
            captured: list[list[str]] = []

            def fake_run(args, check=True, capture=False, quiet=False):
                captured.append(list(args))
                return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr="")

            with mock.patch.object(self.cb, "run", side_effect=fake_run):
                with mock.patch.object(self.cb, "guard_workspace"):
                    self.cb.create_container("clankbox-test", directory)
            self.assertTrue(captured)
            args = captured[0]
            self.assertNotIn("--replace", args)
            self.assertIn(f"{self.cb.LABEL_SCHEMA}={self.cb.SCHEMA_VERSION}", args)


class CmdRmArgsTests(ClankboxTestCase):
    def test_rm_help_does_not_call_podman(self):
        calls: list[list[str]] = []

        def fake_run(args, check=True, capture=False, quiet=False):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with mock.patch.object(self.cb, "run", side_effect=fake_run):
            with self.assertRaises(SystemExit) as ctx:
                self.cb.cmd_rm(["--help"])
            self.assertEqual(ctx.exception.code, 0)
        self.assertEqual(calls, [])

    def test_rm_typo_does_not_remove(self):
        calls: list[list[str]] = []

        def fake_run(args, check=True, capture=False, quiet=False):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with mock.patch.object(self.cb, "run", side_effect=fake_run):
            with self.assertRaises(SystemExit):
                self.cb.cmd_rm(["--al"])
        self.assertEqual(calls, [])

    def test_rm_legacy_schema_removes(self):
        directory = Path("/tmp/project-legacy-rm")
        name = self.cb.container_name(directory)
        calls: list[list[str]] = []

        def fake_run(args, check=True, capture=False, quiet=False):
            calls.append(list(args))
            if args[:2] == ["podman", "rm"]:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            return _label_run_factory(self.cb, directory, schema="2")(
                args, check=check, capture=capture, quiet=quiet
            )

        with mock.patch.object(self.cb, "need_podman", return_value="/usr/bin/podman"):
            with mock.patch.object(self.cb, "workdir", return_value=directory):
                with mock.patch.object(self.cb, "container_lock") as lock:
                    lock.return_value.__enter__ = lambda s: None
                    lock.return_value.__exit__ = lambda *a: None
                    with mock.patch.object(self.cb, "run", side_effect=fake_run):
                        self.cb.cmd_rm([])
        self.assertTrue(
            any(c[:3] == ["podman", "rm", "-f"] and name in c for c in calls)
        )


class UpdateExitTests(ClankboxTestCase):
    def test_update_failure_exits_nonzero(self):
        directory = Path("/tmp/proj")
        with mock.patch.object(self.cb, "need_podman", return_value="/usr/bin/podman"):
            with mock.patch.object(self.cb, "workdir", return_value=directory):
                with mock.patch.object(self.cb, "guard_workspace"):
                    with mock.patch.object(self.cb, "container_lock") as lock:
                        lock.return_value.__enter__ = lambda s: None
                        lock.return_value.__exit__ = lambda *a: None
                        with mock.patch.object(self.cb, "ensure_running"):
                            with mock.patch.object(
                                self.cb, "_update_one", return_value=1
                            ):
                                with self.assertRaises(SystemExit) as ctx:
                                    self.cb.cmd_update([])
                                self.assertNotEqual(ctx.exception.code, 0)


class ExecTtyTests(ClankboxTestCase):
    def test_no_tty_without_terminals(self):
        captured: list[list[str]] = []

        def fake_execvp(file, args):
            captured.append(list(args))
            raise SystemExit(0)

        with mock.patch.object(self.cb, "container_has_x11", return_value=False):
            with mock.patch.object(sys.stdin, "isatty", return_value=False):
                with mock.patch.object(sys.stdout, "isatty", return_value=False):
                    with mock.patch.object(os, "execvp", side_effect=fake_execvp):
                        with self.assertRaises(SystemExit):
                            self.cb.exec_in("ctr", ["bash"])
        self.assertIn("-i", captured[0])
        self.assertNotIn("-t", captured[0])

    def test_tty_when_interactive(self):
        captured: list[list[str]] = []

        def fake_execvp(file, args):
            captured.append(list(args))
            raise SystemExit(0)

        with mock.patch.object(self.cb, "container_has_x11", return_value=False):
            with mock.patch.object(sys.stdin, "isatty", return_value=True):
                with mock.patch.object(sys.stdout, "isatty", return_value=True):
                    with mock.patch.object(os, "execvp", side_effect=fake_execvp):
                        with self.assertRaises(SystemExit):
                            self.cb.exec_in("ctr", ["bash"])
        self.assertIn("-t", captured[0])
        self.assertIn("-i", captured[0])


class ArtifactsTests(ClankboxTestCase):
    def test_embedded_artifacts(self):
        data = self.cb.ARTIFACTS
        self.assertIn("node", data)
        self.assertIn("opencode", data)
        self.assertIn("x64-baseline", data["opencode"]["sha256"])
        script = self.cb.build_provision_script()
        self.assertIn(data["node"]["version"], script)
        self.assertIn(data["opencode"]["version"], script)
        self.assertIn(data["opencode"]["sha256"]["x64-baseline"], script)
        self.assertIn("sha256sum -c", script)
        self.assertNotIn("opencode.ai/install", script)
        self.assertIn(data["debian_image"], self.cb.DOCKERFILE)


class HelpOrderTests(ClankboxTestCase):
    def test_list_help_before_podman(self):
        with mock.patch.object(self.cb, "need_podman") as need:
            with self.assertRaises(SystemExit) as ctx:
                self.cb.cmd_list(["--help"])
            self.assertEqual(ctx.exception.code, 0)
            need.assert_not_called()


if __name__ == "__main__":
    unittest.main()
