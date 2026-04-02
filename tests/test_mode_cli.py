from unittest.mock import patch

from typer.testing import CliRunner

from odoo_venv.cli.main import app
from odoo_venv.utils import Preset

FAKE_PRESETS = {
    "common": Preset(
        description="common preset",
        ignore_from_addons_dirs_requirements="azure-identity",
    ),
    "local": Preset(
        description="local dev preset",
        ignore_from_addons_dirs_requirements="azure-identity",
        install_addons_dirs_requirements=True,
    ),
}

runner = CliRunner()
_BASE_ARGS = ["create", "--odoo-dir", "/opt/odoo"]
_MOCK_VERSION = patch("odoo_venv.cli.main.get_odoo_version_from_release", return_value="17.0")


class TestModeFlag:
    """Verify --mode flag behavior."""

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_default_mode_is_conservative(self, mock_create, mock_detect, mock_load, mock_ver):
        result = runner.invoke(app, [*_BASE_ARGS])
        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["mode"] == "conservative"

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_mode_modern(self, mock_create, mock_detect, mock_load, mock_ver):
        result = runner.invoke(app, [*_BASE_ARGS, "--mode", "modern"])
        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["mode"] == "modern"

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_mode_bleeding_edge(self, mock_create, mock_detect, mock_load, mock_ver):
        result = runner.invoke(app, [*_BASE_ARGS, "--mode", "bleeding-edge"])
        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["mode"] == "bleeding-edge"

    def test_invalid_mode_rejected(self):
        result = runner.invoke(app, ["create", "--mode", "invalid", "--odoo-dir", "/opt/odoo"])
        assert result.exit_code != 0

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_mode_with_preset_orthogonal(self, mock_create, mock_detect, mock_load, mock_ver):
        """--preset local --mode modern: both values forwarded independently."""
        result = runner.invoke(app, [*_BASE_ARGS, "--preset", "local", "--mode", "modern"])
        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        assert kwargs["mode"] == "modern"
        assert kwargs["install_addons_dirs_requirements"] is True


class TestReportFlag:
    """--report is only valid with bleeding-edge mode."""

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_report_with_bleeding_edge_ok(self, mock_create, mock_detect, mock_load, mock_ver):
        result = runner.invoke(app, [*_BASE_ARGS, "--mode", "bleeding-edge", "--report"])
        assert result.exit_code == 0, result.output

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_report_without_bleeding_edge_errors(self, mock_create, mock_detect, mock_load, mock_ver):
        result = runner.invoke(app, [*_BASE_ARGS, "--mode", "conservative", "--report"])
        assert result.exit_code != 0
        assert "bleeding-edge" in result.output
