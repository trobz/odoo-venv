"""Unit tests for ovx: addon series detection, venv resolution, clone, argv, DB naming."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from odoo_venv.cli.ovx_cmd import app
from odoo_venv.exceptions import OdooVenvError
from odoo_venv.ovx import (
    _resolve_addons_path,
    build_odoo_argv,
    make_ephemeral_db_name,
    run_ovx,
    run_with_db_lifecycle,
    user_supplied_db,
)
from odoo_venv.ovx_resolver import ResolvedVenv, clone_venv, install_missing_python_deps, resolve_base_venv
from odoo_venv.utils import write_venv_config

# ---------------------------------------------------------------------------
# Phase 1 — get_addon_series
# ---------------------------------------------------------------------------


class TestGetAddonSeries:
    def test_missing_manifest(self, tmp_path):
        from odoo_venv.exceptions import OdooVenvError
        from odoo_venv.ovx_resolver import get_addon_series

        addon = tmp_path / "my_addon"
        addon.mkdir()
        with pytest.raises(OdooVenvError, match=r"__manifest__\.py"):
            get_addon_series(addon)

    def test_not_a_directory(self, tmp_path):
        from odoo_venv.exceptions import OdooVenvError
        from odoo_venv.ovx_resolver import get_addon_series

        fake_file = tmp_path / "not_a_dir"
        fake_file.write_text("x")
        with pytest.raises(OdooVenvError, match="not a directory"):
            get_addon_series(fake_file)


# ---------------------------------------------------------------------------
# Phase 2 — resolve_base_venv
# ---------------------------------------------------------------------------


def _make_venv(path: Path, odoo_version: str) -> Path:
    """Create a minimal fake odoo-venv directory."""
    path.mkdir(parents=True, exist_ok=True)
    write_venv_config(path, {"python_version": "3.10"}, odoo_version=odoo_version)
    return path


class TestResolveBaseVenv:
    def test_explicit_venv_matching_version(self, tmp_path):
        venv = _make_venv(tmp_path / ".venv", "19.0")
        resolved = resolve_base_venv("19.0", venv_dir=venv, cwd=tmp_path, odoo_dir=None)
        assert resolved.path == venv
        assert resolved.fresh is False
        assert resolved.source == "explicit"

    def test_explicit_venv_version_mismatch(self, tmp_path):
        venv = _make_venv(tmp_path / ".venv", "17.0")
        with pytest.raises(OdooVenvError, match=r"17\.0"):
            resolve_base_venv("19.0", venv_dir=venv, cwd=tmp_path, odoo_dir=None)

    def test_discover_single_match(self, tmp_path):
        _make_venv(tmp_path / ".venv", "19.0")
        resolved = resolve_base_venv("19.0", venv_dir=None, cwd=tmp_path, odoo_dir=None)
        assert resolved.path == tmp_path / ".venv"
        assert resolved.source == "discovered"

    def test_discover_multiple_matches_ambiguous(self, tmp_path):
        _make_venv(tmp_path / ".venv1", "19.0")
        _make_venv(tmp_path / ".venv2", "19.0")
        with pytest.raises(OdooVenvError, match="disambiguate"):
            resolve_base_venv("19.0", venv_dir=None, cwd=tmp_path, odoo_dir=None)

    def test_discover_no_match_with_odoo_dir(self, tmp_path):
        odoo_dir = tmp_path / "odoo"
        odoo_dir.mkdir()
        resolved = resolve_base_venv("19.0", venv_dir=None, cwd=tmp_path, odoo_dir=odoo_dir)
        assert resolved.fresh is True
        assert resolved.source == "fresh"
        assert resolved.path is None

    def test_discover_no_match_no_odoo_dir(self, tmp_path):
        with pytest.raises(OdooVenvError, match="--odoo-dir"):
            resolve_base_venv("19.0", venv_dir=None, cwd=tmp_path, odoo_dir=None)

    def test_version_filter_ignores_wrong_series(self, tmp_path):
        _make_venv(tmp_path / ".venv", "17.0")
        # No 19.0 venv found, no odoo_dir → error
        with pytest.raises(OdooVenvError, match="--odoo-dir"):
            resolve_base_venv("19.0", venv_dir=None, cwd=tmp_path, odoo_dir=None)


# ---------------------------------------------------------------------------
# Phase 2 — clone_venv (filesystem-level; no real Python venv needed)
# ---------------------------------------------------------------------------


class TestCloneVenv:
    def test_clone_produces_copy(self, tmp_path):
        base = tmp_path / "base_venv"
        base.mkdir()
        (base / "pyvenv.cfg").write_text("home = /usr/bin\nprompt = base\n")
        (base / "bin").mkdir()
        (base / "bin" / "python").write_text("#!/bin/python\n")

        clone_dir, cleanup = clone_venv(base)
        try:
            assert (clone_dir / "pyvenv.cfg").exists()
            assert (clone_dir / "bin" / "python").exists()
        finally:
            cleanup()

    def test_clone_does_not_mutate_base(self, tmp_path):
        base = tmp_path / "base_venv"
        base.mkdir()
        (base / "pyvenv.cfg").write_text("home = /usr/bin\n")
        original_content = (base / "pyvenv.cfg").read_text()

        clone_dir, cleanup = clone_venv(base)
        try:
            # Mutate the clone
            (clone_dir / "pyvenv.cfg").write_text("home = /mutated\n")
            # Base must be unchanged
            assert (base / "pyvenv.cfg").read_text() == original_content
        finally:
            cleanup()

    def test_clone_patches_pyvenv_cfg(self, tmp_path):
        base = tmp_path / "base_venv"
        base.mkdir()
        (base / "pyvenv.cfg").write_text("home = /usr/bin\nprompt = base_venv\n")

        clone_dir, cleanup = clone_venv(base)
        try:
            cfg = (clone_dir / "pyvenv.cfg").read_text()
            # prompt should be updated to clone dir name, not base name
            assert "base_venv" not in cfg or str(clone_dir.name) in cfg
        finally:
            cleanup()


# ---------------------------------------------------------------------------
# Phase 2 — install_missing_python_deps
# ---------------------------------------------------------------------------


class TestInstallMissingPythonDeps:
    @patch("odoo_venv.ovx_resolver.subprocess.run")
    @patch("odoo_venv.ovx_resolver._freeze_venv", return_value={"requests": "2.31.0"})
    def test_installs_missing(self, mock_freeze, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0)
        manifest = {"external_dependencies": {"python": ["requests", "fakepkg"]}}
        installed = install_missing_python_deps(tmp_path, manifest)

        assert "fakepkg" in installed
        assert "requests" not in installed
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "fakepkg" in cmd

    @patch("odoo_venv.ovx_resolver.subprocess.run")
    @patch("odoo_venv.ovx_resolver._freeze_venv", return_value={"requests": "2.31.0", "fakepkg": "1.0"})
    def test_skips_already_installed(self, mock_freeze, mock_run, tmp_path):
        manifest = {"external_dependencies": {"python": ["requests", "fakepkg"]}}
        installed = install_missing_python_deps(tmp_path, manifest)

        assert installed == []
        mock_run.assert_not_called()

    @patch("odoo_venv.ovx_resolver.subprocess.run")
    @patch("odoo_venv.ovx_resolver._freeze_venv", return_value={})
    def test_no_python_deps(self, mock_freeze, mock_run, tmp_path):
        manifest = {"external_dependencies": {}}
        installed = install_missing_python_deps(tmp_path, manifest)

        assert installed == []
        mock_run.assert_not_called()

    @patch("odoo_venv.ovx_resolver.subprocess.run")
    @patch("odoo_venv.ovx_resolver._freeze_venv", return_value={})
    def test_no_external_dependencies_key(self, mock_freeze, mock_run, tmp_path):
        installed = install_missing_python_deps(tmp_path, {})
        assert installed == []
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 3 — build_odoo_argv
# ---------------------------------------------------------------------------


class TestBuildOdooArgv:
    def test_basic_argv(self, tmp_path):
        venv = tmp_path / "venv"
        addon = tmp_path / "my_addon"
        addons_path = [str(addon.parent)]
        db = "testdb"

        argv = build_odoo_argv(venv, [addon], addons_path, db, extra_args=[])
        assert str(venv / "bin" / "python") == argv[0]
        assert "-m" in argv
        assert "odoo" in argv
        assert "-i" in argv
        idx = argv.index("-i")
        assert argv[idx + 1] == "my_addon"
        assert "--addons-path" in argv
        assert "-d" in argv
        idx_d = argv.index("-d")
        assert argv[idx_d + 1] == db

    def test_extra_args_appended(self, tmp_path):
        venv = tmp_path / "venv"
        addon = tmp_path / "my_addon"
        argv = build_odoo_argv(venv, [addon], [], "testdb", extra_args=["--log-level=debug"])
        assert "--log-level=debug" in argv

    def test_two_module_argv(self, tmp_path):
        venv = tmp_path / "venv"
        parent_a = tmp_path / "src_a"
        parent_b = tmp_path / "src_b"
        addon_a = parent_a / "mod_a"
        addon_b = parent_b / "mod_b"
        addons_path = [str(parent_a), str(parent_b)]

        argv = build_odoo_argv(venv, [addon_a, addon_b], addons_path, "testdb", extra_args=[])
        idx_i = argv.index("-i")
        assert argv[idx_i + 1] == "mod_a,mod_b"
        idx_ap = argv.index("--addons-path")
        assert str(parent_a) in argv[idx_ap + 1]
        assert str(parent_b) in argv[idx_ap + 1]

    def test_user_dash_d_in_extras_detected(self, tmp_path):
        extra_args = ["-d", "mydb"]
        assert user_supplied_db(extra_args) is True

    def test_user_database_in_extras_detected(self, tmp_path):
        assert user_supplied_db(["--database", "mydb"]) is True
        assert user_supplied_db(["--log-level=debug"]) is False


# ---------------------------------------------------------------------------
# Phase 4 — make_ephemeral_db_name
# ---------------------------------------------------------------------------


class TestMakeEphemeralDbName:
    def test_max_length(self):
        name = make_ephemeral_db_name(["a" * 100])
        assert len(name) <= 63

    def test_uniqueness(self):
        names = {make_ephemeral_db_name(["addon"]) for _ in range(10)}
        assert len(names) == 10

    def test_multi_module_joined(self):
        name = make_ephemeral_db_name(["mod_a", "mod_b"])
        assert re.match(r"^ovx_mod_a_mod_b_[0-9a-f]{8}$", name), name

    def test_length_cap_multi_module(self):
        long_names = ["a" * 30, "b" * 30]
        name = make_ephemeral_db_name(long_names)
        assert len(name) <= 63
        assert re.match(r"^ovx_[a-z0-9_]+_[0-9a-f]{8}$", name), name

    def test_single_module(self):
        name = make_ephemeral_db_name(["my_addon"])
        assert re.match(r"^ovx_my_addon_[0-9a-f]{8}$", name), name


# ---------------------------------------------------------------------------
# Phase 4 — run_with_db_lifecycle
# ---------------------------------------------------------------------------


class FakePopen:
    def __init__(self, returncode=0):
        self._rc = returncode

    def wait(self):
        return self._rc

    def send_signal(self, sig):
        pass


class TestRunWithDbLifecycle:
    @patch("odoo_venv.ovx.subprocess.run")
    @patch("odoo_venv.ovx.subprocess.Popen")
    def test_ephemeral_db_dropped_on_clean_exit(self, mock_popen, mock_run):
        mock_popen.return_value = FakePopen(0)
        mock_run.return_value = MagicMock(returncode=0)

        rc = run_with_db_lifecycle(["fake_odoo", "-d", "ovx_test_abc12345"], db_name="ovx_test_abc12345")

        assert rc == 0
        drop_calls = [c for c in mock_run.call_args_list if "dropdb" in str(c) or "DROP" in str(c)]
        assert len(drop_calls) >= 1

    @patch("odoo_venv.ovx.subprocess.run")
    @patch("odoo_venv.ovx.subprocess.Popen")
    def test_user_supplied_db_not_dropped(self, mock_popen, mock_run):
        mock_popen.return_value = FakePopen(0)
        mock_run.return_value = MagicMock(returncode=0)

        rc = run_with_db_lifecycle(["fake_odoo", "-d", "mydb"], db_name=None)

        assert rc == 0
        drop_calls = [c for c in mock_run.call_args_list if "dropdb" in str(c) or "DROP" in str(c)]
        assert len(drop_calls) == 0

    @patch("odoo_venv.ovx.subprocess.run")
    @patch("odoo_venv.ovx.subprocess.Popen")
    def test_nonzero_exit_still_drops(self, mock_popen, mock_run):
        mock_popen.return_value = FakePopen(1)
        mock_run.return_value = MagicMock(returncode=0)

        rc = run_with_db_lifecycle(["fake_odoo", "-d", "ovx_test_abc12345"], db_name="ovx_test_abc12345")

        assert rc == 1
        drop_calls = [c for c in mock_run.call_args_list if "dropdb" in str(c) or "DROP" in str(c)]
        assert len(drop_calls) >= 1


# ---------------------------------------------------------------------------
# Phase 5 — _resolve_addons_path with extra paths
# ---------------------------------------------------------------------------


class TestResolveAddonsPath:
    def _make_resolved_existing(self, tmp_path: Path, stored_paths: list[str]):
        venv = tmp_path / "venv"
        venv.mkdir()
        write_venv_config(
            venv,
            {"addons_path": ",".join(stored_paths)} if stored_paths else {},
            odoo_version="17.0",
        )
        return ResolvedVenv(path=venv, fresh=False, source="explicit")

    def test_merges_stored_extra_parent(self, tmp_path):
        resolved = self._make_resolved_existing(tmp_path, ["/a", "/b"])
        addon = tmp_path / "my_addon"
        addon.mkdir()
        result = _resolve_addons_path(resolved, [addon], extra=["/c"])
        assert result == ["/a", "/b", "/c", str(addon.parent)]

    def test_dedups_preserving_order(self, tmp_path):
        resolved = self._make_resolved_existing(tmp_path, ["/a", "/b"])
        addon = tmp_path / "my_addon"
        addon.mkdir()
        result = _resolve_addons_path(resolved, [addon], extra=["/b", "/c", str(addon.parent)])
        assert result == ["/a", "/b", "/c", str(addon.parent)]
        assert result.count("/b") == 1
        assert result.count(str(addon.parent)) == 1

    def test_fresh_venv_includes_extra_and_addon_parent(self, tmp_path):
        resolved = ResolvedVenv(path=None, fresh=True, source="fresh")
        addon = tmp_path / "my_addon"
        addon.mkdir()
        result = _resolve_addons_path(resolved, [addon], extra=["/x"])
        assert str(addon.parent) in result
        assert "/x" in result

    def test_addons_path_order_venv_extra_parents(self, tmp_path):
        resolved = self._make_resolved_existing(tmp_path, ["/venv_stored"])
        parent_a = tmp_path / "src_a"
        parent_b = tmp_path / "src_b"
        addon_a = parent_a / "mod_a"
        addon_b = parent_b / "mod_b"
        parent_a.mkdir()
        parent_b.mkdir()
        addon_a.mkdir()
        addon_b.mkdir()

        result = _resolve_addons_path(resolved, [addon_a, addon_b], extra=["/x"])
        assert result.index("/venv_stored") < result.index("/x")
        assert result.index("/x") < result.index(str(parent_a))
        assert result.index(str(parent_a)) < result.index(str(parent_b))

    def test_shared_parent_deduped(self, tmp_path):
        resolved = self._make_resolved_existing(tmp_path, [])
        shared = tmp_path / "addons"
        addon_a = shared / "mod_a"
        addon_b = shared / "mod_b"
        shared.mkdir()
        addon_a.mkdir()
        addon_b.mkdir()

        result = _resolve_addons_path(resolved, [addon_a, addon_b])
        assert result.count(str(shared)) == 1

    def test_extra_already_in_venv_config_deduped(self, tmp_path):
        resolved = self._make_resolved_existing(tmp_path, ["/x"])
        addon = tmp_path / "my_addon"
        addon.mkdir()
        result = _resolve_addons_path(resolved, [addon], extra=["/x"])
        assert result.count("/x") == 1
        assert result.index("/x") == 0


# ---------------------------------------------------------------------------
# Phase 5 — run_ovx with addons_path forwarding
# ---------------------------------------------------------------------------


class TestRunOvxAddonsPath:
    @patch("odoo_venv.ovx.run_with_db_lifecycle", return_value=0)
    @patch("odoo_venv.ovx.create_launcher")
    @patch("odoo_venv.ovx.install_missing_python_deps", return_value=[])
    @patch("odoo_venv.ovx.clone_venv")
    @patch("odoo_venv.ovx.resolve_base_venv")
    @patch("odoo_venv.ovx.get_addon_series", return_value="17.0")
    def test_extra_addons_appear_in_argv(
        self,
        mock_series,
        mock_resolve,
        mock_clone,
        mock_missing,
        mock_launcher,
        mock_run,
        tmp_path,
    ):
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "bin").mkdir()
        (venv / "bin" / "python").write_text("#!/bin/python")
        write_venv_config(venv, {}, odoo_version="17.0")

        addon = tmp_path / "my_addon"
        addon.mkdir()
        (addon / "__manifest__.py").write_text('{"name": "T", "version": "17.0.1.0.0"}')

        mock_resolve.return_value = ResolvedVenv(path=venv, fresh=False, source="explicit")
        mock_clone.return_value = (venv, lambda: None)

        run_ovx(
            [addon],
            venv_dir=venv,
            odoo_dir=None,
            database="testdb",
            keep_clone=False,
            no_launcher=True,
            extra_args=[],
            cwd=tmp_path,
            addons_path=["/extra/path"],
        )

        called_argv = mock_run.call_args[0][0]
        addons_path_val = called_argv[called_argv.index("--addons-path") + 1]
        assert "/extra/path" in addons_path_val

    @patch("odoo_venv.ovx.create_odoo_venv")
    @patch("odoo_venv.ovx.run_with_db_lifecycle", return_value=0)
    @patch("odoo_venv.ovx.create_launcher")
    @patch("odoo_venv.ovx.resolve_base_venv")
    @patch("odoo_venv.ovx.get_addon_series", return_value="17.0")
    def test_fresh_venv_receives_all_addons_paths(
        self,
        mock_series,
        mock_resolve,
        mock_launcher,
        mock_run,
        mock_create_venv,
        tmp_path,
    ):
        odoo_dir = tmp_path / "odoo"
        odoo_dir.mkdir()
        addon = tmp_path / "my_addon"
        addon.mkdir()
        (addon / "__manifest__.py").write_text('{"name": "T", "version": "17.0.1.0.0"}')

        fresh_venv = tmp_path / "fresh_venv" / "odoo-17.0-venv"

        def fake_create_venv(**kwargs):
            fresh_venv.mkdir(parents=True, exist_ok=True)
            (fresh_venv / "bin").mkdir(exist_ok=True)
            (fresh_venv / "bin" / "python").write_text("#!/bin/python")

        mock_create_venv.side_effect = fake_create_venv
        mock_resolve.return_value = ResolvedVenv(path=None, fresh=True, source="fresh")
        mock_run.return_value = 0

        run_ovx(
            [addon],
            venv_dir=None,
            odoo_dir=odoo_dir,
            database="testdb",
            keep_clone=True,
            no_launcher=True,
            extra_args=[],
            cwd=tmp_path,
            addons_path=["/oca/path"],
        )

        call_kwargs = mock_create_venv.call_args[1]
        assert str(addon.parent) in call_kwargs["addons_paths"]
        assert "/oca/path" in call_kwargs["addons_paths"]

    @patch("odoo_venv.ovx.run_with_db_lifecycle", return_value=0)
    @patch("odoo_venv.ovx.create_launcher")
    @patch("odoo_venv.ovx.install_missing_python_deps", return_value=[])
    @patch("odoo_venv.ovx.clone_venv")
    @patch("odoo_venv.ovx.resolve_base_venv")
    @patch("odoo_venv.ovx.get_addon_series", return_value="17.0")
    def test_deps_union_called_once(
        self,
        mock_series,
        mock_resolve,
        mock_clone,
        mock_missing,
        mock_launcher,
        mock_run,
        tmp_path,
    ):
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "bin").mkdir()
        (venv / "bin" / "python").write_text("#!/bin/python")
        write_venv_config(venv, {}, odoo_version="17.0")

        addon_a = tmp_path / "mod_a"
        addon_a.mkdir()
        (addon_a / "__manifest__.py").write_text(
            '{"name": "A", "version": "17.0.1.0.0", "external_dependencies": {"python": ["requests", "lxml"]}}'
        )
        addon_b = tmp_path / "mod_b"
        addon_b.mkdir()
        (addon_b / "__manifest__.py").write_text(
            '{"name": "B", "version": "17.0.1.0.0", "external_dependencies": {"python": ["lxml", "Pillow"]}}'
        )

        mock_resolve.return_value = ResolvedVenv(path=venv, fresh=False, source="explicit")
        mock_clone.return_value = (venv, lambda: None)

        run_ovx(
            [addon_a, addon_b],
            venv_dir=venv,
            odoo_dir=None,
            database="testdb",
            keep_clone=False,
            no_launcher=True,
            extra_args=[],
            cwd=tmp_path,
        )

        mock_missing.assert_called_once()
        called_manifest = mock_missing.call_args[0][1]
        deps = called_manifest["external_dependencies"]["python"]
        assert deps == ["requests", "lxml", "Pillow"]


# ---------------------------------------------------------------------------
# Phase 5 — CLI flag parsing in ovx_cmd
# ---------------------------------------------------------------------------


class TestOvxCmdAddonsPathFlag:
    @patch("odoo_venv.cli.ovx_cmd.run_ovx", return_value=0)
    def test_csv_parsed_to_resolved_paths(self, mock_run_ovx, tmp_path):
        addon = tmp_path / "my_addon"
        addon.mkdir()
        (addon / "__manifest__.py").write_text('{"name": "T", "version": "17.0.1.0.0"}')

        extra_a = tmp_path / "extra_a"
        extra_b = tmp_path / "extra_b"
        extra_a.mkdir()
        extra_b.mkdir()

        runner = CliRunner()
        runner.invoke(app, [str(addon), "--addons-path", f"{extra_a},{extra_b}"])

        assert mock_run_ovx.called
        kwargs = mock_run_ovx.call_args[1]
        assert str(extra_a.resolve()) in kwargs["addons_path"]
        assert str(extra_b.resolve()) in kwargs["addons_path"]

    @patch("odoo_venv.cli.ovx_cmd.run_ovx", return_value=0)
    def test_no_flag_passes_empty_list(self, mock_run_ovx, tmp_path):
        addon = tmp_path / "my_addon"
        addon.mkdir()
        (addon / "__manifest__.py").write_text('{"name": "T", "version": "17.0.1.0.0"}')

        runner = CliRunner()
        runner.invoke(app, [str(addon)])

        assert mock_run_ovx.called
        kwargs = mock_run_ovx.call_args[1]
        assert kwargs["addons_path"] == []

    @patch("odoo_venv.cli.ovx_cmd.run_ovx", return_value=0)
    def test_multi_addon_paths_resolved(self, mock_run_ovx, tmp_path):
        addon_a = tmp_path / "mod_a"
        addon_b = tmp_path / "mod_b"
        addon_a.mkdir()
        addon_b.mkdir()
        (addon_a / "__manifest__.py").write_text('{"name": "A", "version": "17.0.1.0.0"}')
        (addon_b / "__manifest__.py").write_text('{"name": "B", "version": "17.0.1.0.0"}')

        runner = CliRunner()
        runner.invoke(app, [f"{addon_a},{addon_b}"])

        assert mock_run_ovx.called
        args = mock_run_ovx.call_args[0][0]
        assert len(args) == 2
        assert args[0] == addon_a.resolve()
        assert args[1] == addon_b.resolve()

    @patch("odoo_venv.cli.ovx_cmd.run_ovx", return_value=0)
    def test_empty_entry_raises_bad_parameter(self, mock_run_ovx, tmp_path):
        addon = tmp_path / "mod_a"
        addon.mkdir()

        runner = CliRunner()
        result = runner.invoke(app, [f"{addon},"])

        assert result.exit_code != 0
        assert not mock_run_ovx.called
