---
icon: lucide/git-compare
description: "odoo-venv compare — compare installed package versions across virtual environments."
tags:
  - cli
  - reference
  - compare
---

# `odoo-venv compare`

Compare installed package versions across virtual environments.

```bash
odoo-venv compare VENV_DIRS... [OPTIONS]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `VENV_DIRS` | Yes | One or more virtual environment directories to compare. |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--no-latest` | `False` | Do not fetch or show the "Latest" column from PyPI. |

## Example

```bash
odoo-venv compare .venv-17 .venv-18
```
