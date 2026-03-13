---
icon: lucide/plus-circle
description: "odoo-venv create — create a virtual environment to run Odoo with full options reference."
tags:
  - cli
  - reference
  - create
  - venv
---

# `odoo-venv create`

Create a virtual environment to run Odoo.

```bash
odoo-venv create [ODOO_VERSION] [OPTIONS]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `ODOO_VERSION` | No | Odoo version, e.g. `19.0`. Inferred from `--project-dir` if omitted. |

## Options

### Core options

| Option | Default | Description |
|--------|---------|-------------|
| `--python-version`, `-p` | Auto | Python version. Auto-selected based on Odoo version if omitted. |
| `--venv-dir` | `./.venv` | Path to create the virtual environment. |
| `--odoo-dir` | Auto | Path to Odoo source code. |
| `--addons-path` | — | Comma-separated list of addons paths. |
| `--preset` | — | Use a preset of options. Preset values can be overridden by other options. |
| `--project-dir` | — | Path to project directory. Auto-detects `--addons-path`, `--odoo-dir` and applies `--preset=project`. |

### Install controls

| Option | Default | Description |
|--------|---------|-------------|
| `--install-odoo` / `--no-install-odoo` | `True` | Install Odoo in editable mode. |
| `--install-odoo-requirements` / `--no-install-odoo-requirements` | `True` | Install packages from Odoo's `requirements.txt`. |
| `--install-addons-dirs-requirements` / `--no-install-addons-dirs-requirements` | `False` | Install `requirements.txt` found in addons paths. |
| `--install-addons-manifests-requirements` / `--no-install-addons-manifests-requirements` | `False` | Install requirements from addons' `__manifest__.py` files. |

### Ignore lists

| Option | Description |
|--------|-------------|
| `--ignore-from-odoo-requirements` | Comma-separated packages to skip from Odoo's `requirements.txt`. |
| `--ignore-from-addons-dirs-requirements` | Comma-separated packages to skip from addons' `requirements.txt`. |
| `--ignore-from-addons-manifests-requirements` | Comma-separated packages to skip from addons' manifests. |

### Extra packages

| Option | Description |
|--------|-------------|
| `--extra-requirements-file` | Path to an extra requirements file. |
| `--extra-requirement` | Comma-separated list of extra packages. Use `\,` for a literal comma. |

### Behavior

| Option | Default | Description |
|--------|---------|-------------|
| `--verbose` | `False` | Display more details. |
| `--dry-run` | `False` | Show what would be done without doing it. |
| `--skip-on-failure` / `--no-skip-on-failure` | `False` | Automatically skip packages that fail to install and retry. |
| `--create-launcher` / `--no-create-launcher` | `False` | Generate a launcher script in `~/.local/bin/`. |
| `--report-errors` | `False` | On failure, automatically open a GitHub issue with the full output. |

## Examples

**Basic usage:**

```bash
odoo-venv create 19.0 --odoo-dir ~/code/odoo/odoo/19.0
```

**With addons and extra packages:**

```bash
odoo-venv create 19.0 \
    --odoo-dir ~/code/odoo/odoo/19.0 \
    --addons-path ~/code/odoo/addons/web,~/code/odoo/addons/mail \
    --install-addons-dirs-requirements \
    --install-addons-manifests-requirements \
    --extra-requirement "debugpy,ipython"
```

**Using a preset:**

```bash
odoo-venv create 19.0 --preset local
```

**Project directory auto-detection:**

```bash
odoo-venv create --project-dir ~/code/my-odoo-project
```

**Dry run to preview:**

```bash
odoo-venv create 19.0 --odoo-dir ~/code/odoo/odoo/19.0 --dry-run --verbose
```
