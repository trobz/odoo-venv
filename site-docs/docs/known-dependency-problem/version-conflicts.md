---
icon: lucide/git-compare
description: "Odoo pins exact dependency versions that conflict with addon requirements. How odoo-venv resolves version conflicts automatically."
tags:
  - troubleshooting
  - dependencies
  - version-conflicts
---

# Version Conflicts

## The error

```
ERROR: Cannot install -r requirements.txt because these package versions
have conflicting dependencies.

The conflict is caused by:
    odoo requirements.txt pins pytz==2016.7
    pandas 1.5.3 depends on pytz>=2020.1
```

## Why it happens

Odoo's `requirements.txt` pins **exact versions** of its dependencies (e.g. `pytz==2016.7`, `python-dateutil==2.5.3`). When an addon requires a package that depends on a newer version of one of these pinned packages, pip/uv cannot resolve the conflict.

This is especially common with data science libraries (`pandas`, `matplotlib`, `altair`) that require modern versions of packages Odoo pins to older releases.

## How odoo-venv solves it

odoo-venv uses two mechanisms:

### 1. User pin auto-override

When your addon's `requirements.txt` or `--extra-requirement` specifies a version constraint for a package that Odoo also pins, **odoo-venv automatically skips Odoo's pin** in favor of yours.

For example, if your addon requires `pytz>=2020.1`, odoo-venv drops Odoo's `pytz==2016.7` pin so the newer version can install.

### 2. Known transitive conflict table

Some packages don't directly pin a conflicting version, but their dependencies do. odoo-venv maintains a table of these known transitive conflicts and auto-relaxes Odoo's pins when the trigger package is detected:

| Trigger package | Odoo pins relaxed |
|----------------|-------------------|
| `matplotlib` | `pyparsing` |
| `google-books-api-wrapper` | `idna` |
| `pandas` | `python-dateutil`, `pytz` |
| `altair` | `python-dateutil`, `pytz` |
| `klaviyo-api` | `requests` |

### How it works

1. odoo-venv scans all user requirement sources (addons dirs, manifests, extra requirements)
2. If a user package has a version constraint conflicting with an Odoo pin, the Odoo pin is dropped
3. If a user package is in the known transitive conflict table, the associated Odoo pins are dropped
4. The relaxed requirements are then installed together without conflicts

Use `--verbose` to see which pins are being auto-ignored:

```
  i  Auto-ignoring Odoo's 'pytz' pin (transitively required by 'pandas')
  i  Auto-ignoring Odoo's 'python-dateutil' pin (transitively required by 'pandas')
```

## Manual workaround

Without odoo-venv, manually remove conflicting pins from Odoo's `requirements.txt` before installing:

```bash
# Remove the conflicting line from requirements.txt
sed -i '/^pytz==/d' ~/code/odoo/odoo/19.0/requirements.txt
pip install -r ~/code/odoo/odoo/19.0/requirements.txt
pip install pandas
```

!!! warning
    Editing Odoo's `requirements.txt` directly modifies tracked files in the Odoo repo. Consider using a wrapper script or `--ignore-from-odoo-requirements` instead.
