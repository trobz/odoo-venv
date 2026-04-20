from unittest.mock import patch

from typer.testing import CliRunner

from odoo_venv.cli.main import app
from odoo_venv.main import VenvResult
from odoo_venv.utils import write_venv_config

runner = CliRunner()

_VENV_ARGS = {
    "preset": "",
    "python_version": "3.10",
    "odoo_dir": "/opt/odoo",
    "venv_dir": "",  # filled per test
    "addons_path": "",
    "install_odoo": True,
    "install_odoo_requirements": True,
    "ignore_from_odoo_requirements": "",
    "install_addons_dirs_requirements": False,
    "ignore_from_addons_dirs_requirements": "",
    "install_addons_manifests_requirements": False,
    "ignore_from_addons_manifests_requirements": "",
    "extra_requirements_file": "",
    "extra_requirement": "debugpy",
    "skip_on_failure": False,
    "create_launcher": False,
    "project_dir": "",
}


def _create_fake_venv(tmp_path):
    """Create a fake venv dir with .odoo-venv.toml and pyvenv.cfg."""
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("uv = 0.7.0\n")
    (venv_dir / "bin").mkdir()
    args = {**_VENV_ARGS, "venv_dir": str(venv_dir)}
    write_venv_config(venv_dir, args, "18.0")
    return venv_dir


class TestUpdateCommand:
    @patch("odoo_venv.cli.main._freeze_venv", return_value={"debugpy": "1.8.0"})
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_update_basic(self, mock_create, mock_freeze, tmp_path):
        venv_dir = _create_fake_venv(tmp_path)
        tmp_venv = venv_dir.parent / f"{venv_dir.name}.tmp"

        def _side_effect(**kwargs):
            tmp_venv.mkdir(exist_ok=True)
            (tmp_venv / "pyvenv.cfg").write_text("uv = 0.7.0\n")
            return VenvResult()

        mock_create.side_effect = _side_effect
        # Confirm the interactive prompt with "y"
        result = runner.invoke(app, ["update", str(venv_dir)], input="y\n")
        assert result.exit_code == 0, result.output
        mock_create.assert_called_once()

    def test_update_missing_toml(self, tmp_path):
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        result = runner.invoke(app, ["update", str(venv_dir)])
        assert result.exit_code != 0
        assert ".odoo-venv.toml" in result.output

    def test_update_nonexistent_dir(self, tmp_path):
        result = runner.invoke(app, ["update", str(tmp_path / "nope")])
        assert result.exit_code != 0

    @patch("odoo_venv.cli.main._freeze_venv", return_value={"debugpy": "1.8.0"})
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_update_backup_created(self, mock_create, mock_freeze, tmp_path):
        venv_dir = _create_fake_venv(tmp_path)
        tmp_venv = venv_dir.parent / f"{venv_dir.name}.tmp"

        def _side_effect(**kwargs):
            tmp_venv.mkdir(exist_ok=True)
            (tmp_venv / "pyvenv.cfg").write_text("uv = 0.7.0\n")
            return VenvResult()

        mock_create.side_effect = _side_effect
        result = runner.invoke(app, ["update", str(venv_dir), "--backup"], input="y\n")
        assert result.exit_code == 0, result.output
        bak_path = venv_dir.parent / f"{venv_dir.name}.bak"
        assert bak_path.exists()

    @patch("odoo_venv.cli.main._freeze_venv", return_value={"debugpy": "1.8.0"})
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_update_no_backup(self, mock_create, mock_freeze, tmp_path):
        venv_dir = _create_fake_venv(tmp_path)
        tmp_venv = venv_dir.parent / f"{venv_dir.name}.tmp"

        def _side_effect(**kwargs):
            tmp_venv.mkdir(exist_ok=True)
            (tmp_venv / "pyvenv.cfg").write_text("uv = 0.7.0\n")
            return VenvResult()

        mock_create.side_effect = _side_effect
        result = runner.invoke(app, ["update", str(venv_dir), "--no-backup"], input="y\n")
        assert result.exit_code == 0, result.output
        bak_path = venv_dir.parent / f"{venv_dir.name}.bak"
        assert not bak_path.exists()

    @patch("odoo_venv.cli.main._freeze_venv", return_value={"debugpy": "1.8.0"})
    @patch("odoo_venv.cli.main.create_odoo_venv")
    def test_update_user_declines(self, mock_create, mock_freeze, tmp_path):
        venv_dir = _create_fake_venv(tmp_path)
        tmp_venv = venv_dir.parent / f"{venv_dir.name}.tmp"

        def _side_effect(**kwargs):
            tmp_venv.mkdir(exist_ok=True)
            (tmp_venv / "pyvenv.cfg").write_text("uv = 0.7.0\n")
            return VenvResult()

        mock_create.side_effect = _side_effect
        result = runner.invoke(app, ["update", str(venv_dir)], input="n\n")
        assert "cancelled" in result.output.lower()
        assert venv_dir.exists()

    @patch("odoo_venv.cli.main.create_odoo_venv", side_effect=RuntimeError("build failed"))
    def test_update_create_failure_cleans_tmp(self, mock_create, tmp_path):
        venv_dir = _create_fake_venv(tmp_path)
        result = runner.invoke(app, ["update", str(venv_dir)])
        assert result.exit_code != 0
        tmp_path_check = venv_dir.parent / f"{venv_dir.name}.tmp"
        assert not tmp_path_check.exists()
        # Original untouched
        assert venv_dir.exists()
