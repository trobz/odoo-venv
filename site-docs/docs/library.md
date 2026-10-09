---
icon: lucide/package
description: Use odoo-venv from a Python script via create_odoo_venv.
tags:
  - library
  - api
  - python
---

# Library usage

odoo-venv is importable as a regular Python package — the `odoo-venv` CLI is a
thin [Typer](https://typer.tiangolo.com/) wrapper around the same
`create_odoo_venv` function, so anything the CLI can do, a script can do too.

## `create_odoo_venv`

```python
from odoo_venv import create_odoo_venv

result = create_odoo_venv(
    odoo_version="19.0",
    odoo_dir="~/code/odoo/19.0",
    venv_dir="~/.venvs/odoo19",
    python_version="3.11",
    install_odoo_requirements=True,
    addons_paths=["~/code/odoo/19.0/addons-oca/web"],
    install_addons_dirs_requirements=True,
    extra_requirements=["debugpy"],
    verbose=True,
)

print(result.ignored)
```

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `odoo_version` | `str` | — | Odoo version string (e.g. `"19.0"`), used to evaluate requirement markers. |
| `odoo_dir` | `Path \| str` | — | Path to the Odoo source checkout. |
| `venv_dir` | `str` | — | Path where the virtual environment is created. |
| `python_version` | `str \| None` | — | Python version to use; auto-detected from `odoo/__init__.py` when `None`. |
| `install_odoo` | `bool` | `True` | Install Odoo itself into the venv. |
| `install_odoo_requirements` | `bool` | `True` | Install `odoo_dir/requirements.txt`. |
| `ignore_from_odoo_requirements` | `str \| None` | `None` | Comma-separated package names to skip from Odoo's requirements. |
| `addons_paths` | `list[str] \| None` | `None` | Extra addons directories to scan. |
| `install_addons_dirs_requirements` | `bool` | `False` | Install each addons path's own `requirements.txt`. |
| `ignore_from_addons_dirs_requirements` | `str \| None` | `None` | Comma-separated package names to skip from addons-dir requirements. |
| `install_addons_manifests_requirements` | `bool` | `False` | Install Python packages declared in addon manifests (`external_dependencies.python`). |
| `ignore_from_addons_manifests_requirements` | `str \| None` | `None` | Comma-separated package names to skip from manifest-derived requirements. |
| `extra_requirements_file` | `str \| None` | `None` | Path to an additional requirements file to install. |
| `extra_requirements` | `list[str] \| None` | `None` | Additional individual package specs to install. |
| `extra_commands` | `list[dict] \| None` | `None` | Extra shell commands to run at `after_venv`, `after_requirements`, or `after_odoo_install` stages. |
| `verbose` | `bool` | `False` | Print detailed progress and command output. |
| `skip_on_failure` | `bool` | `False` | Skip packages that fail to install instead of aborting. |
| `force` | `bool` | `False` | Recreate the venv if it already exists. |
| `ignore_sources` | `dict[str, str] \| None` | `None` | Pre-resolved map of ignored package to source label, used internally by the CLI. |

The function returns a `VenvResult` dataclass carrying an `ignored` mapping of
packages skipped per source.

## Notes

Each parameter above mirrors a CLI flag on `odoo-venv create` — `addons_paths`
is `--addons-path` (repeatable), `install_addons_dirs_requirements` is
`--install-addons-dirs-requirements`, and so on. See
[`odoo-venv create` reference](reference/page-1.md) for the full flag list and
their defaults on the command line.
