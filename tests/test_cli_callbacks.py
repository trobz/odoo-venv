from unittest.mock import patch

from typer.testing import CliRunner

from odoo_venv.cli.main import app
from odoo_venv.utils import Preset

# Two fake presets used throughout the tests
FAKE_PRESETS = {
    "common": Preset(
        description="common preset",
        extra_requirement="setuptools",
        ignore_from_odoo_requirements="badpkg",
        ignore_from_addons_dirs_requirements="azure-identity",
    ),
    # Non-common presets simulate what load_presets() returns in production:
    # common's fields are already merged into each preset.
    "local": Preset(
        description="local dev preset",
        extra_requirement="setuptools,debugpy,ipython",
        ignore_from_odoo_requirements="badpkg",
        ignore_from_addons_dirs_requirements="azure-identity",
        install_addons_dirs_requirements=True,
    ),
    "project": Preset(
        description="project preset",
        extra_requirement="setuptools,pdfminer.six,fonttools",
        ignore_from_odoo_requirements="badpkg",
        ignore_from_addons_dirs_requirements="azure-identity",
        extra_requirements_file="./requirements.txt",
        install_addons_dirs_requirements=False,
    ),
}

runner = CliRunner()

# --odoo-dir is required; version is inferred from it via get_odoo_version_from_release
_BASE_ARGS = ["create", "--odoo-dir", "/opt/odoo"]

# Shared mock: version inference from --odoo-dir always returns "17.0"
_MOCK_VERSION = patch("odoo_venv.cli.main.get_odoo_version_from_release", return_value="17.0")


class TestPresetOrdering:
    """Verify that --preset and --project-dir interact correctly regardless of arg order.

    These tests use CliRunner so Typer handles argument parsing and fires the
    is_eager callbacks in the same order a real user invocation would.
    """

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_preset_before_project_dir(self, mock_create, mock_detect, mock_load, mock_ver):
        """--preset local --project-dir /opt/project: preset fires first, project preset skipped."""
        result = runner.invoke(app, [*_BASE_ARGS, "--preset", "local", "--project-dir", "/opt/project"])

        assert result.exit_code == 0, result.output
        # "local" preset's install_addons_dirs_requirements=True should have been applied
        _, kwargs = mock_create.call_args
        assert kwargs["install_addons_dirs_requirements"] is True
        # "local" preset packages should be in extra_requirements
        assert "debugpy" in kwargs["extra_requirements"]
        assert "ipython" in kwargs["extra_requirements"]
        # "project" preset packages must NOT appear (project was skipped)
        assert "pdfminer.six" not in kwargs["extra_requirements"]
        assert kwargs["ignore_from_odoo_requirements"] == "badpkg"

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_project_dir_before_preset(self, mock_create, mock_detect, mock_load, mock_ver):
        """--project-dir /opt/project --preset local: project-dir fires first but local wins."""
        result = runner.invoke(app, [*_BASE_ARGS, "--project-dir", "/opt/project", "--preset", "local"])

        assert result.exit_code == 0, result.output
        # Final state must reflect "local" preset, not "project"
        _, kwargs = mock_create.call_args
        assert kwargs["install_addons_dirs_requirements"] is True
        assert "debugpy" in kwargs["extra_requirements"]
        assert "ipython" in kwargs["extra_requirements"]
        assert "pdfminer.six" not in kwargs["extra_requirements"]

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_project_dir_without_preset(self, mock_create, mock_detect, mock_load, mock_ver):
        """--project-dir /opt/project (no --preset): "project" preset is auto-applied silently."""
        result = runner.invoke(app, [*_BASE_ARGS, "--project-dir", "/opt/project"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["install_addons_dirs_requirements"] is False
        assert "pdfminer.six" in kwargs["extra_requirements"]
        assert "fonttools" in kwargs["extra_requirements"]


class TestExtraRequirementAdditive:
    """--extra-requirement must add to preset packages, not replace them."""

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_extra_requirement_merges_with_preset(self, mock_create, mock_detect, mock_load, mock_ver):
        """--preset local --extra-requirement=mypkg: final list = preset + CLI packages."""
        result = runner.invoke(app, [*_BASE_ARGS, "--preset", "local", "--extra-requirement", "mypkg"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        extra = kwargs["extra_requirements"]
        assert "setuptools" in extra
        assert "debugpy" in extra
        assert "ipython" in extra
        assert "mypkg" in extra
        assert len(extra) == 4

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_no_extra_requirement_uses_preset_only(self, mock_create, mock_detect, mock_load, mock_ver):
        """--preset local (no --extra-requirement): only preset packages."""
        result = runner.invoke(app, [*_BASE_ARGS, "--preset", "local"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["extra_requirements"] == ["setuptools", "debugpy", "ipython"]

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_extra_requirement_without_preset(self, mock_create, mock_detect, mock_load, mock_ver):
        """--extra-requirement=mypkg (no preset): common + CLI package."""
        result = runner.invoke(app, [*_BASE_ARGS, "--extra-requirement", "mypkg"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        # common preset is applied by default, so setuptools is included
        assert "setuptools" in kwargs["extra_requirements"]
        assert "mypkg" in kwargs["extra_requirements"]


class TestDefaultCommonPreset:
    """When no --preset and no --project-dir, common preset is applied by default."""

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_no_preset_applies_common(self, mock_create, mock_detect, mock_load, mock_ver):
        """No --preset and no --project-dir: common preset is applied."""
        result = runner.invoke(app, [*_BASE_ARGS])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert "setuptools" in kwargs["extra_requirements"]

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_no_preset_applies_common_default_map_fields(self, mock_create, mock_detect, mock_load, mock_ver):
        """No --preset: common's default_map fields (ignore_from_*) reach function params."""
        result = runner.invoke(app, [*_BASE_ARGS])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["ignore_from_odoo_requirements"] == "badpkg"
        assert kwargs["ignore_from_addons_dirs_requirements"] == "azure-identity"

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_cli_flag_overrides_common_default(self, mock_create, mock_detect, mock_load, mock_ver):
        """Explicit --ignore-from-odoo-requirements overrides common preset value."""
        result = runner.invoke(app, [*_BASE_ARGS, "--ignore-from-odoo-requirements", "mypkg"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["ignore_from_odoo_requirements"] == "mypkg"

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_explicit_preset_skips_default_common(self, mock_create, mock_detect, mock_load, mock_ver):
        """--preset local: common is already merged into local via load_presets, no double-apply."""
        result = runner.invoke(app, [*_BASE_ARGS, "--preset", "local"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        # local preset's packages should be present (merged via load_presets)
        assert "debugpy" in kwargs["extra_requirements"]
        assert "ipython" in kwargs["extra_requirements"]
