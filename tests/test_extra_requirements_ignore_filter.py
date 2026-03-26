import tempfile
from unittest.mock import patch

from typer.testing import CliRunner

from odoo_venv.cli.main import app
from odoo_venv.utils import Preset

runner = CliRunner()

# --odoo-dir is required; version is inferred from it via get_odoo_version_from_release
_BASE_ARGS = ["create", "--odoo-dir", "/opt/odoo"]

FAKE_PRESETS = {
    "local": Preset(
        description="local dev preset",
        extra_requirement="debugpy,lxml",
        install_addons_dirs_requirements=False,
        ignore_from_odoo_requirements="lxml",
    ),
}

# Shared mock: version inference from --odoo-dir always returns "17.0"
_MOCK_VERSION = patch("odoo_venv.cli.main.get_odoo_version_from_release", return_value="17.0")


class TestExtraRequirementsNotFiltered:
    """--extra-requirement packages must survive the ignore list."""

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_extra_requirement_not_dropped_when_in_ignore_list(self, mock_create, mock_detect, mock_load, mock_ver):
        """lxml in --extra-requirement must reach create_odoo_venv even though the
        preset also sets ignore_from_odoo_requirements=lxml.

        The CLI layer does not filter extra_requirements; it passes them verbatim.
        The fix ensures create_odoo_venv also does not filter them.
        """
        result = runner.invoke(
            app,
            [*_BASE_ARGS, "--preset", "local", "--extra-requirement", "lxml>=4.9.3"],
        )

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        # lxml must appear in extra_requirements passed to create_odoo_venv
        assert "lxml>=4.9.3" in kwargs["extra_requirements"]

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_preset_extra_requirement_and_ignore_coexist(self, mock_create, mock_detect, mock_load, mock_ver):
        """When a preset both ignores lxml and lists it in extra_requirement, the
        extra_requirement value must still reach create_odoo_venv unchanged.
        """
        result = runner.invoke(app, [*_BASE_ARGS, "--preset", "local"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        # Both packages from the preset must be forwarded
        assert "lxml" in kwargs["extra_requirements"]
        assert "debugpy" in kwargs["extra_requirements"]
        # The ignore flag must also be forwarded
        assert kwargs["ignore_from_odoo_requirements"] == "lxml"


class TestExtraRequirementsFileNotFiltered:
    """Verify that packages from --extra-requirements-file bypass the ignore map."""

    @_MOCK_VERSION
    @patch("odoo_venv.cli.main.load_presets", return_value=FAKE_PRESETS)
    @patch("odoo_venv.cli.main._detect_project_layout", return_value=(None, None, None))
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_extra_requirements_file_forwarded_with_ignored_package(
        self, mock_create, mock_detect, mock_load, mock_ver
    ):
        """A requirements file containing lxml must be forwarded to create_odoo_venv
        unchanged even though the preset sets ignore_from_odoo_requirements=lxml.

        The CLI passes the file path as-is; create_odoo_venv is responsible for
        reading it with an empty ignore map (the fix) so lxml is never dropped.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("lxml>=4.9\ndebugpy\n")
            req_file = f.name

        result = runner.invoke(
            app,
            [*_BASE_ARGS, "--preset", "local", "--extra-requirements-file", req_file],
        )

        assert result.exit_code == 0, result.output
        _, kwargs = mock_create.call_args
        # File path forwarded verbatim — create_odoo_venv reads it with {} ignore map
        assert kwargs["extra_requirements_file"] == req_file
        # Ignore flag still forwarded (applies only to Odoo's requirements.txt)
        assert kwargs["ignore_from_odoo_requirements"] == "lxml"
