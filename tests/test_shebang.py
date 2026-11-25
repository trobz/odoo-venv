"""Tests for rewriting broken uv build-env shebangs in bin/odoo."""

from pathlib import Path

from odoo_venv.main import _fix_odoo_script_shebang


def test_fix_odoo_script_shebang_rewrites_ephemeral_uv_path(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    script = venv / "bin" / "odoo"
    script.write_text(
        "#!/home/user/.cache/uv/builds-v0/.tmp8NaMaB/bin/python\nimport odoo\nodoo.cli.main()\n",
        encoding="utf-8",
    )

    assert _fix_odoo_script_shebang(venv) is True
    assert script.read_text(encoding="utf-8") == (
        f"#!{venv.resolve() / 'bin' / 'python'}\nimport odoo\nodoo.cli.main()\n"
    )
    # Second call is a no-op.
    assert _fix_odoo_script_shebang(venv) is False


def test_fix_odoo_script_shebang_skips_missing_or_non_shebang(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    assert _fix_odoo_script_shebang(venv) is False

    (venv / "bin").mkdir(parents=True)
    script = venv / "bin" / "odoo"
    script.write_text("import odoo\n", encoding="utf-8")
    assert _fix_odoo_script_shebang(venv) is False
    assert script.read_text(encoding="utf-8") == "import odoo\n"
