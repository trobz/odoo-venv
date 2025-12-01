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

For recurring configurations, you can define presets in a `presets.toml` file, in `~/.local/share/odoo-venv/`.

There are 4 out-of-box presets: local, demo, project, ci (see [src/odoo_venv/assets/presets.toml](src/odoo_venv/assets/presets.toml))

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
