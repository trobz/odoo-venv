# odoo-venv

A command-line tool to spin up isolated Odoo dev environment in seconds.

## Installation
```bash
pip install odoo-venv
```

## Quick Start


### 1. Direct CLI Arguments

**Example:**

```bash
odoo-venv create 17.0 \
    --odoo-dir ~/code/odoo/odoo/17.0 \
    --addons-path ~/code/odoo/addons/web,~/code/odoo/addons/mail \
    --python-version 3.10 \
    --install-addons-dirs-requirements \
    --extra-requirement "debugpy,ipython"
```

This command creates a virtual environment for Odoo 17.0 with the following specifications:
- Odoo source is located at `~/code/odoo/odoo/17.0`.
- Additional addons are in `~/code/odoo/addons/web` and `~/code/odoo/addons/mail`.
- The environment uses Python 3.10.
- It installs dependencies from `requirements.txt` files found in the addons paths.
- It also installs `debugpy` and `ipython`.

### 2. Using Presets

The tool includes 4 built-in presets: local, demo, project, ci (see [odoo_venv/assets/presets.toml](odoo_venv/assets/presets.toml))

**Example:**

```bash
odoo-venv create 17.0 \
    --odoo-dir ~/code/odoo/odoo/17.0 \
    --addons-path ~/code/odoo/addons/web,~/code/odoo/addons/mail \
    --preset demo
```

This command will apply all the options from the `demo` preset. You can still override any preset option by providing a direct CLI argument. For example, to use a different `extra_requirement` for a specific run:

```bash
odoo-venv create 17.0 \
    --odoo-dir ~/code/odoo/odoo/17.0 \
    --addons-path ~/code/odoo/addons/web,~/code/odoo/addons/mail \
    --preset demo \
    --extra-requirement "pylint"
```

### 3. As a Library

The tool can also be used as lib in a custom python script

**Example:**

```python
from odoo_venv import create_odoo_venv

create_odoo_venv(
    odoo_version="17.0",
    odoo_dir="~/code/odoo/odoo/17.0",
    venv_dir="./.venv",
    python_version="3.10",
    addons_paths=["~/code/odoo/addons/web", "~/code/odoo/addons/mail"],
    install_addons_dirs_requirements=True,
    extra_requirements=["debugpy", "ipython"],
)
```

## ovx — on-the-fly module runner

`ovx` is a companion command that runs an Odoo addon instantly — like `npx`/`uvx` for Odoo. It detects the required Odoo series from the addon's `__manifest__.py`, finds or creates a matching venv, installs any missing Python dependencies, and launches Odoo with `-i <module>`. The database is ephemeral by default and is dropped on exit.

Multiple addons can be passed as a comma-separated list. The first addon's manifest decides the Odoo series; mismatched modules will fail at Odoo's module-not-found error. Paths containing commas are not supported.

```bash
# Auto-discover a matching venv in the current directory:
ovx ./crm_eav_fields

# Run multiple addons in a single ephemeral DB:
ovx ./module_a,~/oca/module_b

# Explicit venv:
ovx ./crm_eav_fields --venv-dir ~/code/foo/.venv

# Fresh-create a venv (requires Odoo source):
ovx ./crm_eav_fields --odoo-dir ~/code/odoo/19.0

# Named, persistent database (not dropped on exit):
ovx ./crm_eav_fields -d my_dev_db

# Pass extra arguments through to Odoo:
ovx ./crm_eav_fields -- --log-level=debug --workers 0

# Extra addons paths (e.g. enterprise/OCA) merged with the venv's stored addons_path:
ovx ./my-addon --odoo-dir ~/odoo --addons-path ~/enterprise,~/oca/server-tools
```

> **`--addons-path`** accepts a comma-separated list of extra paths. They are merged with the venv's stored `addons_path` and the addon's own parent directory (deduped, order preserved). When no venv is found and a fresh one is created, the paths are also passed to `create_odoo_venv` so Python deps declared in enterprise/OCA manifests are installed during venv build.

### Venv resolution priority

| Priority | Condition | Outcome |
|----------|-----------|---------|
| 1 | `--venv-dir` provided | Use it; error if Odoo version mismatches |
| 2 | Exactly one venv found under CWD matching the addon's series | Use it |
| 3 | Multiple matches | Error — pass `--venv-dir` to disambiguate |
| 4 | No match, `--odoo-dir` provided | Create a fresh venv |
| 5 | No match, no `--odoo-dir` | Error |

### Database lifecycle

By default `ovx` generates a unique ephemeral DB name (`ovx_<joined_modules>_<hex8>`) and drops it when Odoo exits — even on Ctrl-C or non-zero exit. Pass `-d <name>` to use a named, persistent database instead (no automatic create or drop).

## Development

To test with a clean state (no cached packages):

```bash
uv cache clean --force
```
