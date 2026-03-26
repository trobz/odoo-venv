from pathlib import Path

from typer.testing import CliRunner

from odoo_venv.cli.main import (
    _discover_venvs,
    _read_venv_info,
    app,
)
from odoo_venv.utils import write_venv_config

runner = CliRunner()


def _make_odoo_venv(path: Path, *, preset: str = "common", python: str = "3.10", odoo: str = "18.0"):
    """Create a minimal odoo-venv directory with .odoo-venv.toml."""
    path.mkdir(parents=True, exist_ok=True)
    write_venv_config(path, {"preset": preset, "python_version": python}, odoo_version=odoo)


# --- _discover_venvs ---


def test_discover_venvs_finds_nested(tmp_path):
    _make_odoo_venv(tmp_path / "proj" / ".venv")
    _make_odoo_venv(tmp_path / "other" / "venv", odoo="17.0")

    result = _discover_venvs(tmp_path)
    assert len(result) == 2
    assert tmp_path / "other" / "venv" in result
    assert tmp_path / "proj" / ".venv" in result


def test_discover_venvs_skips_noise_dirs(tmp_path):
    for d in (".git", "node_modules", "__pycache__"):
        _make_odoo_venv(tmp_path / d)

    assert _discover_venvs(tmp_path) == []


def test_discover_venvs_no_descend_into_venv(tmp_path):
    """A nested venv inside another venv should not be discovered."""
    _make_odoo_venv(tmp_path / ".venv")
    _make_odoo_venv(tmp_path / ".venv" / "lib" / "nested_venv", odoo="17.0")

    result = _discover_venvs(tmp_path)
    assert result == [tmp_path / ".venv"]


def test_discover_venvs_empty(tmp_path):
    assert _discover_venvs(tmp_path) == []


def test_discover_venvs_ignores_plain_venv(tmp_path):
    """A plain venv (pyvenv.cfg only, no .odoo-venv.toml) should not appear."""
    plain = tmp_path / ".venv"
    plain.mkdir()
    (plain / "pyvenv.cfg").write_text("version = 3.10.12\n")

    assert _discover_venvs(tmp_path) == []


# --- _read_venv_info ---


def test_read_venv_info_from_config(tmp_path):
    """All fields from .odoo-venv.toml in a single pass."""
    write_venv_config(tmp_path, {"preset": "community", "python_version": "3.10"}, odoo_version="18.0")
    info = _read_venv_info(tmp_path)
    assert info == {"python": "3.10", "odoo": "18.0", "preset": "community"}


# --- CLI integration ---


def test_list_no_venvs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No virtual environments found" in result.output


def test_list_with_venvs_from_config(tmp_path, monkeypatch):
    """Venv with .odoo-venv.toml shows all columns including PRESET."""
    _make_odoo_venv(tmp_path / ".venv", preset="enterprise", python="3.10", odoo="18.0")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert ".venv" in result.output
    assert "3.10" in result.output
    assert "18.0" in result.output
    assert "enterprise" in result.output
