from pathlib import Path

from typer.testing import CliRunner

from odoo_venv.cli.main import (
    _collect_external_deps_from_manifests,
    _find_module_manifests,
    app,
)

runner = CliRunner()


# --- Fixtures ---


def _make_module(addons_dir: Path, name: str, python: list[str] | None = None, deb: list[str] | None = None) -> Path:
    """Create a minimal Odoo module with a manifest under *addons_dir*."""
    module_dir = addons_dir / name
    module_dir.mkdir(parents=True, exist_ok=True)
    ext_deps: dict = {}
    if python is not None:
        ext_deps["python"] = python
    if deb is not None:
        ext_deps["deb"] = deb
    manifest = {"name": name, "external_dependencies": ext_deps}
    (module_dir / "__manifest__.py").write_text(repr(manifest))
    return module_dir


# --- _find_module_manifests ---


def test_find_module_manifests_specific_modules(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale")
    _make_module(addons, "purchase")
    _make_module(addons, "stock")

    found = _find_module_manifests(["sale", "stock"], [str(addons)])

    assert set(found) == {"sale", "stock"}
    assert all(p.name == "__manifest__.py" for p in found.values())


def test_find_module_manifests_all_modules(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale")
    _make_module(addons, "purchase")

    found = _find_module_manifests(None, [str(addons)])

    assert set(found) == {"sale", "purchase"}


def test_find_module_manifests_skips_dirs_without_manifest(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale")
    (addons / "not_a_module").mkdir()  # no __manifest__.py

    found = _find_module_manifests(None, [str(addons)])

    assert set(found) == {"sale"}


def test_find_module_manifests_first_addons_path_wins(tmp_path):
    addons1 = tmp_path / "addons1"
    addons2 = tmp_path / "addons2"
    _make_module(addons1, "sale")
    _make_module(addons2, "sale")

    found = _find_module_manifests(["sale"], [str(addons1), str(addons2)])

    assert found["sale"].parent.parent == addons1


def test_find_module_manifests_missing_module(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale")

    found = _find_module_manifests(["nonexistent"], [str(addons)])

    assert found == {}


def test_find_module_manifests_nonexistent_addons_dir(tmp_path):
    found = _find_module_manifests(None, [str(tmp_path / "does_not_exist")])
    assert found == {}


# --- _collect_external_deps_from_manifests ---


def test_collect_python_deps(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale", python=["requests", "stdnum"])
    found = _find_module_manifests(["sale"], [str(addons)])

    deps = _collect_external_deps_from_manifests(found, "python")

    assert "requests" in deps
    assert "python-stdnum" in deps  # import-to-pip mapping applied
    assert deps["requests"] == ["sale"]


def test_collect_deb_deps(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale", deb=["wkhtmltopdf"])
    found = _find_module_manifests(["sale"], [str(addons)])

    deps = _collect_external_deps_from_manifests(found, "deb")

    assert deps == {"wkhtmltopdf": ["sale"]}


def test_collect_deps_aggregates_modules(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale", python=["requests"])
    _make_module(addons, "purchase", python=["requests", "lxml"])
    found = _find_module_manifests(None, [str(addons)])

    deps = _collect_external_deps_from_manifests(found, "python")

    assert set(deps["requests"]) == {"sale", "purchase"}
    assert deps["lxml"] == ["purchase"]


def test_collect_deps_empty_when_kind_absent(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale", python=["requests"])
    found = _find_module_manifests(["sale"], [str(addons)])

    deps = _collect_external_deps_from_manifests(found, "deb")

    assert deps == {}


def test_collect_deps_no_external_dependencies(tmp_path):
    addons = tmp_path / "addons"
    module_dir = addons / "sale"
    module_dir.mkdir(parents=True)
    (module_dir / "__manifest__.py").write_text("{'name': 'sale'}")
    found = _find_module_manifests(["sale"], [str(addons)])

    deps = _collect_external_deps_from_manifests(found, "python")

    assert deps == {}


# --- CLI integration ---


def test_cli_default_kind_is_python(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale", python=["requests"])

    result = runner.invoke(app, ["list-external-dependencies", "--addons-path", str(addons)])

    assert result.exit_code == 0
    assert "requests" in result.output


def test_cli_explicit_kind_deb(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale", deb=["wkhtmltopdf"])

    result = runner.invoke(app, ["list-external-dependencies", "--kind", "deb", "--addons-path", str(addons)])

    assert result.exit_code == 0
    assert "wkhtmltopdf" in result.output


def test_cli_filter_by_modules(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale", python=["requests"])
    _make_module(addons, "purchase", python=["lxml"])

    result = runner.invoke(app, ["list-external-dependencies", "--addons-path", str(addons), "--modules", "sale"])

    assert result.exit_code == 0
    assert "requests" in result.output
    assert "lxml" not in result.output


def test_cli_warns_on_missing_module(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale", python=["requests"])

    result = runner.invoke(
        app, ["list-external-dependencies", "--addons-path", str(addons), "--modules", "sale,nonexistent"]
    )

    assert result.exit_code == 0
    assert "nonexistent" in result.output


def test_cli_no_deps_found(tmp_path):
    addons = tmp_path / "addons"
    _make_module(addons, "sale")

    result = runner.invoke(app, ["list-external-dependencies", "--addons-path", str(addons)])

    assert result.exit_code == 0
    assert "No 'python' external dependencies found" in result.output


def test_cli_requires_addons_path_or_project_dir():
    result = runner.invoke(app, ["list-external-dependencies"])

    assert result.exit_code != 0 or "error" in result.output


def test_cli_multiple_addons_paths(tmp_path):
    addons1 = tmp_path / "addons1"
    addons2 = tmp_path / "addons2"
    _make_module(addons1, "sale", python=["requests"])
    _make_module(addons2, "purchase", python=["lxml"])

    result = runner.invoke(
        app,
        ["list-external-dependencies", "--addons-path", f"{addons1},{addons2}"],
    )

    assert result.exit_code == 0
    assert "requests" in result.output
    assert "lxml" in result.output
