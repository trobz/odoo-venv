from pathlib import Path
from unittest.mock import patch

import pytest

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
    """Run create_odoo_venv in dry-run mode and return the temp requirements file contents.

    Patches os.remove to capture the temp file path before deletion.
    Accepts any create_odoo_venv kwarg to override defaults.
    """
    captured = []
    original_remove = __import__("os").remove

    with patch("odoo_venv.main.os.remove", side_effect=lambda p: captured.append(p)):
        create_odoo_venv(
            odoo_version=kwargs.pop("odoo_version", "17.0"),
            odoo_dir=odoo_dir,
            venv_dir=tmp_path / ".venv",
            python_version=kwargs.pop("python_version", "3.10"),
            install_odoo=False,
            install_odoo_requirements=True,
            dry_run=True,
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
    """Packages in _KNOWN_TRANSITIVE_CONFLICTS trigger auto-ignore for their mapped Odoo pins."""

    @pytest.mark.parametrize(
        "trigger_pkg, odoo_reqs, dropped_pin",
        [
            ("matplotlib", "pyparsing==2.1.0\n", "pyparsing==2.1.0"),
            ("google-books-api-wrapper", "idna==2.10\n", "idna==2.10"),
        ],
        ids=["matplotlib_pyparsing", "google_books_idna"],
    )
    def test_transitive_pin_skipped(self, tmp_path, trigger_pkg, odoo_reqs, dropped_pin):
        odoo_dir = _make_odoo_dir(tmp_path, odoo_reqs)
        contents = _run_dry(tmp_path, odoo_dir, extra_requirements=[trigger_pkg])
        assert dropped_pin not in contents

    def test_skipped_only_when_in_base_pinned(self, tmp_path):
        # Odoo doesn't pin pyparsing → nothing to skip, no error
        odoo_dir = _make_odoo_dir(tmp_path, "lxml==4.9.3\n")
        contents = _run_dry(tmp_path, odoo_dir, extra_requirements=["matplotlib"])
        assert "lxml==4.9.3" in contents

    def test_not_triggered_without_known_package(self, tmp_path):
        odoo_dir = _make_odoo_dir(tmp_path, "pyparsing==2.1.0\n")
        contents = _run_dry(tmp_path, odoo_dir, extra_requirements=["some-random-package"])
        assert "pyparsing==2.1.0" in contents
