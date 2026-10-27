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
ovx ADDON_PATHS [OPTIONS] [-- ODOO_ARGS...]
```

Resolves the Odoo series from `--odoo-dir`, `--venv-dir`, and every addon's manifest, failing fast if any two disagree. Installs missing Python dependencies, then runs Odoo with `-i <module_a>,<module_b>`. The database is ephemeral by default and is dropped on exit.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `ADDON_PATHS` | Yes | Comma-separated paths to Odoo addon directories (e.g. `./a,~/oca/b`). Each must contain `__manifest__.py`. Paths containing commas are not supported. |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--venv-dir` | — | Explicit venv to use (must match the addon's Odoo series). |
| `--odoo-dir` | — | Odoo source directory. Required on cold start, where it supplies the Odoo source the venv is built from. |
| `-d`, `--database` | — | Named DB to use. Suppresses ephemeral DB creation and cleanup. |
| `--no-launcher` | `False` | Skip launcher script creation. |
| `--addons-path` | — | Extra addons paths (comma-separated) for modules the target addons depend on, e.g. enterprise or OCA checkouts. Merged with the venv's stored `addons_path` and the addons' own parent directories. |

Extra arguments after `--` are forwarded verbatim to Odoo.

## Venv resolution

`ovx` has no CWD-based venv discovery — the same command behaves identically from any working directory. At least one of `--venv-dir` or `--odoo-dir` is required:

| Flags | Outcome |
|---|---|
| Neither `--venv-dir` nor `--odoo-dir` | Hard error before any work, exit 1 |
| `--venv-dir` points at an existing directory | Warm path — use that venv as the base |
| `--venv-dir` missing or pointing at a non-existent path | Cold start — see below |

### First run (cold start)

Cold start requires **both** flags:

- If `--venv-dir` is not set at all, `ovx` refuses with `FreshVenvRequiresVenvDirError` ("no venv exists yet; pass `--venv-dir` to choose where to create it").
- If `--venv-dir` is set but doesn't exist yet and `--odoo-dir` is not set, series resolution fails first with `VenvCreationRequiresOdooDirError` — there's no Odoo source to build from or declared series to confirm against.

When both are present and `--venv-dir` doesn't exist yet, `ovx` prompts:

```
No venv at <dir>. Create an Odoo <series> venv there?
```

The default answer is **yes**. Declining prints `Aborted: no venv created.` and `ovx` exits with code **1**.

With no interactive terminal on stdin, `ovx` does not prompt — it raises `NonInteractiveVenvCreationError`, which points at the CI recipe: pre-build the venv up front with

```bash
odoo-venv create --venv-dir <dir> --odoo-dir <odoo source>
```

`ovx` will never build a venv unattended.

The venv built on confirmation is **permanent** (not thrown away after the run) and equivalent to `odoo-venv create`, with one deliberate difference: addon manifest dependencies are **not** installed into it. The base stays a clean Odoo-only environment; each run's extra packages land in a throwaway clone instead (see below). The venv's `[common]` preset values are applied automatically.

If the build fails or is interrupted, a partial venv is removed — but only when it has no `.odoo-venv.toml` yet. A venv that got far enough to write its config is kept, so a failed run cannot permanently block the directory.

## Clone (conditional)

Addon dependencies are **not always** cloned into a separate venv. The base venv is used directly unless something is actually missing:

1. Every target addon's `external_dependencies.python` from its `__manifest__.py` is unioned, deduped, in first-seen order.
2. That dependency list is checked against the base venv's installed packages. If it's empty, no subprocess is spawned at all — the common case costs nothing.
3. **Nothing missing → no clone.** Odoo runs from the base venv directly.
4. **Something missing → clone**, then the missing packages are installed into the clone only, with `uv pip install --python <clone> <pkgs>`.

Mechanism, for anyone debugging an unexpected clone:

- The clone target is a fresh `tempfile.mkdtemp(prefix="ovx_clone_")` directory containing a copy named after the base venv.
- The copy is `cp --reflink=auto -r` — copy-on-write on btrfs/apfs — falling back to `shutil.copytree(symlinks=True)` when `cp` exits non-zero. Hard links (`cp -l`) are deliberately **not** used: mutating the clone would mutate the base.
- `pyvenv.cfg` in the clone is rewritten so its `prompt =` reflects the clone, not the base.
- The temp directory is removed automatically once the run finishes.
- Known sharp edge: dependency matching does not parse PEP 508 specifiers, so a manifest entry like `paramiko<4.0.0` never matches an installed `paramiko` and is always reported missing — that run always clones.

## Series resolution

Every one of these contributes a candidate Odoo series:

- `--odoo-dir` → read from `odoo/release.py`. Raises an error when the directory has no readable release info.
- `--venv-dir` → the `odoo_version` recorded in the venv's `.odoo-venv.toml`.
- **Each** addon path → the version declared in its own `__manifest__.py`.

If two of these contribute *different* known series, `ovx` raises a conflicting-series error listing every participant and its value. If none of them declares a series at all, it raises an undetermined-series error. An addon declaring no series (Odoo core, Enterprise) contributes nothing and is legal, as long as another participant supplies the series.

## Ephemeral DB lifecycle

By default `ovx` generates a unique DB name from the target addon directory names: each name is sanitised to `[a-z0-9_]`, the names are joined with `_`, truncated to 50 chars, then suffixed with 8 random hex characters — `ovx_<module_a>_<module_b>_<hex8>`. This DB is dropped when Odoo exits — even on Ctrl-C or non-zero exit.

Pass `-d <name>` to opt out: the named DB is used as-is and is **not** dropped after the run.

## Examples

**Fresh-create a venv from Odoo source (first run at that `--venv-dir`):**

```bash
ovx ./crm_eav_fields --odoo-dir ~/code/odoo/19.0 --venv-dir ~/code/venvs/19.0
```

**Explicit, already-existing venv:**

```bash
ovx ./crm_eav_fields --venv-dir ~/code/foo/.venv
```

**Named, persistent database:**

```bash
ovx ./crm_eav_fields --venv-dir ~/code/foo/.venv -d my_dev_db
```

**Pass extra arguments through to Odoo:**

```bash
ovx ./crm_eav_fields --venv-dir ~/code/foo/.venv -- --log-level=debug --workers 0
```

**Multiple addons:**

```bash
ovx ./module_a,~/oca/module_b --venv-dir ~/code/venvs/18.0
```

**Extra addons paths, for dependencies the target addons need:**

```bash
ovx ./my-addon --venv-dir ~/code/venvs/19.0 --addons-path ~/enterprise,~/oca/server-tools
```
