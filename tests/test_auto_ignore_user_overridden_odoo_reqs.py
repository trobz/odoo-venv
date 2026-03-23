import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from odoo_venv.main import (
    create_odoo_venv,
)


def _make_odoo_dir(tmp_path: Path, reqs: str) -> Path:
    """Create a minimal fake Odoo directory with a requirements.txt."""
    odoo_dir = tmp_path / "odoo"
    odoo_dir.mkdir()
    (odoo_dir / "requirements.txt").write_text(reqs, encoding="utf-8")
    return odoo_dir


def _run_dry(tmp_path: Path, odoo_dir: Path, **kwargs) -> str:
    """Run create_odoo_venv with mocked subprocess calls and return the temp requirements file contents.

    Patches os.remove to capture the temp file path before deletion.
    Patches subprocess.run and _run_command to prevent real uv/pip calls
    (tests only check requirement filtering logic).
    Accepts any create_odoo_venv kwarg to override defaults.
    """
    captured = []
    original_remove = __import__("os").remove

    mock_result = MagicMock(spec=subprocess.CompletedProcess)
    mock_result.returncode = 0
    mock_result.stdout = ""

    with (
        patch("odoo_venv.main.os.remove", side_effect=lambda p: captured.append(p)),
        patch("odoo_venv.main.subprocess.run", return_value=mock_result),
        patch("odoo_venv.main._run_command"),
    ):
        create_odoo_venv(
            odoo_version=kwargs.pop("odoo_version", "17.0"),
            odoo_dir=odoo_dir,
            venv_dir=tmp_path / ".venv",
            python_version=kwargs.pop("python_version", "3.10"),
            install_odoo=False,
            install_odoo_requirements=True,
            **kwargs,
        )

    assert captured, "os.remove was never called — temp file was not created"
    tmp_file = Path(captured[0])
    contents = tmp_file.read_text(encoding="utf-8")
    original_remove(str(tmp_file))
    return contents


class TestDirectOverride:
    """When a user passes a versioned specifier that conflicts with Odoo's pin, Odoo's pin is dropped."""

    def test_pin_skipped_when_user_specifies_version(self, tmp_path):
        odoo_dir = _make_odoo_dir(tmp_path, "python-stdnum==1.8\n")
        contents = _run_dry(tmp_path, odoo_dir, extra_requirements=["python-stdnum>=1.9"])
        assert "python-stdnum==1.8" not in contents

    def test_pin_kept_when_no_user_override(self, tmp_path):
        odoo_dir = _make_odoo_dir(tmp_path, "python-stdnum==1.8\n")
        contents = _run_dry(tmp_path, odoo_dir)
        assert "python-stdnum==1.8" in contents

    def test_pin_kept_when_user_specifies_without_version(self, tmp_path):
        odoo_dir = _make_odoo_dir(tmp_path, "python-stdnum==1.8\n")
        contents = _run_dry(tmp_path, odoo_dir, extra_requirements=["python-stdnum"])
        assert "python-stdnum==1.8" in contents

    def test_unrelated_package_unaffected(self, tmp_path):
        odoo_dir = _make_odoo_dir(tmp_path, "python-stdnum==1.8\nlxml==4.9.3\n")
        contents = _run_dry(tmp_path, odoo_dir, extra_requirements=["python-stdnum>=1.9"])
        assert "lxml==4.9.3" in contents

    def test_pin_skipped_via_requirements_file(self, tmp_path):
        odoo_dir = _make_odoo_dir(tmp_path, "python-stdnum==1.8\n")
        req_file = tmp_path / "my_reqs.txt"
        req_file.write_text("python-stdnum>=1.9\n", encoding="utf-8")
        contents = _run_dry(tmp_path, odoo_dir, extra_requirements_file=str(req_file))
        assert "python-stdnum==1.8" not in contents


class TestTransitiveConflict:
    """Transitive conflicts are now handled dynamically by _validate_and_relax()
    (via uv pip compile), not by a static dict.  These tests verify that
    _validate_and_relax() is called during create_odoo_venv() and removes
    conflicting BASE pins from the requirements file when uv reports a conflict.
    """

    def test_base_pin_relaxed_on_compile_conflict(self, tmp_path):
        """When uv pip compile reports a conflict with a BASE pin, it's removed."""
        odoo_dir = _make_odoo_dir(tmp_path, "requests==2.21.0\n")

        captured = []
        original_remove = __import__("os").remove

        # subprocess.run is called multiple times during create_odoo_venv:
        # 1. `uv python find` (python version check) — needs rc=0
        # 2. _validate_and_relax compile attempt — fails with conflict
        # 3. _validate_and_relax retry — succeeds
        compile_results = iter([
            MagicMock(returncode=0, stderr="", stdout=b""),  # uv python find
            MagicMock(returncode=1, stderr="you require requests==2.21.0", stdout=""),  # compile fail
            MagicMock(returncode=0, stderr="", stdout=""),  # compile pass
        ])

        def mock_subprocess_run(cmd, **kwargs):
            return next(compile_results)

        with (
            patch("odoo_venv.main.os.remove", side_effect=lambda p: captured.append(p)),
            patch("odoo_venv.main.subprocess.run", side_effect=mock_subprocess_run),
            patch("odoo_venv.main._run_command"),
        ):
            create_odoo_venv(
                odoo_version="12.0",
                odoo_dir=odoo_dir,
                venv_dir=tmp_path / ".venv",
                python_version="3.7",
                install_odoo=False,
                install_odoo_requirements=True,
                extra_requirements=["klaviyo-api"],
            )

        assert captured, "os.remove was never called — temp file was not created"
        tmp_file = Path(captured[0])
        contents = tmp_file.read_text(encoding="utf-8")
        original_remove(str(tmp_file))
        assert "requests==2.21.0" not in contents

    def test_non_base_pin_not_relaxed(self, tmp_path):
        """When compile succeeds (no conflict), all pins remain."""
        odoo_dir = _make_odoo_dir(tmp_path, "lxml==4.9.3\n")
        # _run_dry already mocks subprocess.run with rc=0, so _validate_and_relax
        # sees no conflict and doesn't modify the file.
        contents = _run_dry(tmp_path, odoo_dir, extra_requirements=["matplotlib"])
        assert "lxml==4.9.3" in contents

    def test_not_triggered_without_known_package(self, tmp_path):
        odoo_dir = _make_odoo_dir(tmp_path, "pyparsing==2.1.0\n")
        contents = _run_dry(tmp_path, odoo_dir, extra_requirements=["some-random-package"])
        assert "pyparsing==2.1.0" in contents
