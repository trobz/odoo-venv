from unittest.mock import patch

from typer.testing import CliRunner

from odoo_venv.cli.main import app
from odoo_venv.utils import Preset

# Two fake presets used throughout the tests
FAKE_PRESETS = {
    "local": Preset(
        description="local dev preset",
        extra_requirement="debugpy,ipython",
        install_addons_dirs_requirements=True,
    ),
    "project": Preset(
        description="project preset",
        extra_requirement="pdfminer.six,fonttools",
        extra_requirements_file="./requirements.txt",
        install_addons_dirs_requirements=False,
    ),
}

runner = CliRunner()

_BASE_ARGS = ["create", "17.0", "--odoo-dir", "/opt/odoo"]


class TestPresetOrdering:
    """Verify that --preset and --project-dir interact correctly regardless of arg order.

    These tests use CliRunner so Typer handles argument parsing and fires the
    is_eager callbacks in the same order a real user invocation would.
    """

    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_preset_before_project_dir(self, mock_create, mock_detect, mock_load):
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

    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_project_dir_before_preset(self, mock_create, mock_detect, mock_load):
        """--project-dir /opt/project --preset local: project-dir fires first but local wins."""
        result = runner.invoke(app, [*_BASE_ARGS, "--project-dir", "/opt/project", "--preset", "local"])

        assert result.exit_code == 0, result.output
        # Final state must reflect "local" preset, not "project"
        _, kwargs = mock_create.call_args
        assert kwargs["install_addons_dirs_requirements"] is True
        assert "debugpy" in kwargs["extra_requirements"]
        assert "ipython" in kwargs["extra_requirements"]
        assert "pdfminer.six" not in kwargs["extra_requirements"]

    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_project_dir_without_preset(self, mock_create, mock_detect, mock_load):
        """--project-dir /opt/project (no --preset): "project" preset is auto-applied silently."""
        result = runner.invoke(app, [*_BASE_ARGS, "--project-dir", "/opt/project"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["install_addons_dirs_requirements"] is False
        assert "pdfminer.six" in kwargs["extra_requirements"]
        assert "fonttools" in kwargs["extra_requirements"]


class TestExtraRequirementAdditive:
    """--extra-requirement must add to preset packages, not replace them."""

    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_extra_requirement_merges_with_preset(self, mock_create, mock_detect, mock_load):
        """--preset local --extra-requirement=mypkg: final list = preset + CLI packages."""
        result = runner.invoke(app, [*_BASE_ARGS, "--preset", "local", "--extra-requirement", "mypkg"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        extra = kwargs["extra_requirements"]
        assert "debugpy" in extra
        assert "ipython" in extra
        assert "mypkg" in extra
        assert len(extra) == 3

    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_no_extra_requirement_uses_preset_only(self, mock_create, mock_detect, mock_load):
        """--preset local (no --extra-requirement): only preset packages."""
        result = runner.invoke(app, [*_BASE_ARGS, "--preset", "local"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["extra_requirements"] == ["debugpy", "ipython"]

    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_extra_requirement_without_preset(self, mock_create, mock_detect, mock_load):
        """--extra-requirement=mypkg (no preset): only CLI package."""
        result = runner.invoke(app, [*_BASE_ARGS, "--extra-requirement", "mypkg"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["extra_requirements"] == ["mypkg"]
