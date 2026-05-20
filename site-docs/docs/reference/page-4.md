---
icon: lucide/zap
description: "ovx — run an Odoo addon on-the-fly, like npx/uvx but for Odoo."
tags:
  - cli
  - reference
  - ovx
  - run
---

# `ovx`

Run an Odoo addon on-the-fly — like `npx`/`uvx` but for Odoo.

```bash
ovx ADDON_PATH [OPTIONS] [-- ODOO_ARGS...]
```

Detects the addon's Odoo series from `__manifest__.py`, resolves or creates a matching venv, installs missing Python dependencies, then runs Odoo with `-i <module>`. The database is ephemeral by default and is dropped on exit.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `ADDON_PATH` | Yes | Path to the Odoo addon directory to run. Must contain `__manifest__.py`. |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--venv-dir` | — | Explicit venv to use. Must match the addon's Odoo series; error if version mismatches. |
| `--odoo-dir` | — | Odoo source directory. Required when no matching venv is found (fresh-create path). |
| `-d`, `--database` | — | Named DB to use. Suppresses ephemeral DB creation and cleanup. |
| `--no-launcher` | `False` | Skip launcher script creation in `~/.local/bin/`. |
| `--` | — | Separator: everything after `--` is forwarded verbatim to Odoo. |

## Venv resolution priority

`ovx` resolves the base venv in the following order:

| Priority | Condition | Outcome |
|----------|-----------|---------|
| 1 | `--venv-dir` provided | Use it; raise an error if the Odoo version mismatches |
| 2 | Exactly one venv found under CWD matching the addon's series | Use it |
| 3 | Multiple matches | Error — pass `--venv-dir` to disambiguate |
| 4 | No match + `--odoo-dir` provided | Create a fresh venv |
| 5 | No match, no `--odoo-dir` | Error |

The resolved venv is **cloned** (copy-on-write where supported) before use, so the base venv is never modified.

## Ephemeral DB lifecycle

By default `ovx` generates a unique DB name (`ovx_<addon>_<hex8>`) and drops it when Odoo exits — even on Ctrl-C or non-zero exit.

Pass `-d <name>` to opt out: the named DB is used as-is and is **not** dropped after the run.

## Examples

**Auto-discover a matching venv:**

```bash
ovx ./crm_eav_fields
```

**Explicit venv:**

```bash
ovx ./crm_eav_fields --venv-dir ~/code/foo/.venv
```

**Fresh-create a venv from Odoo source:**

```bash
ovx ./crm_eav_fields --odoo-dir ~/code/odoo/19.0
```

**Named, persistent database:**

```bash
ovx ./crm_eav_fields -d my_dev_db
```

**Pass extra arguments through to Odoo:**

```bash
ovx ./crm_eav_fields -- --log-level=debug --workers 0
```
