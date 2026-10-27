from pathlib import Path
from unittest.mock import MagicMock, patch

from odoo_venv.main import _run_command, uv_env
from odoo_venv.ovx_resolver import install_python_deps


def test_uv_env_enables_legacy_tar_backend(monkeypatch):
    monkeypatch.delenv("UV_LEGACY_TAR_BACKEND", raising=False)
    assert uv_env()["UV_LEGACY_TAR_BACKEND"] == "1"


def test_uv_env_keeps_user_value(monkeypatch):
    monkeypatch.setenv("UV_LEGACY_TAR_BACKEND", "0")
    assert uv_env()["UV_LEGACY_TAR_BACKEND"] == "0"


@patch("odoo_venv.main.subprocess.run", return_value=MagicMock(returncode=0))
def test_run_command_passes_uv_defaults(mock_run, monkeypatch):
    monkeypatch.delenv("UV_LEGACY_TAR_BACKEND", raising=False)
    _run_command(["uv", "pip", "install", "x"], extra_env={"UV_PRERELEASE": "allow"})

    env = mock_run.call_args.kwargs["env"]
    assert env["UV_LEGACY_TAR_BACKEND"] == "1"
    assert env["UV_PRERELEASE"] == "allow"


@patch("odoo_venv.ovx_resolver.subprocess.run")
def test_install_python_deps_passes_uv_defaults(mock_run, monkeypatch):
    monkeypatch.delenv("UV_LEGACY_TAR_BACKEND", raising=False)
    install_python_deps(Path("/venv"), ["x"])

    assert mock_run.call_args.kwargs["env"]["UV_LEGACY_TAR_BACKEND"] == "1"
