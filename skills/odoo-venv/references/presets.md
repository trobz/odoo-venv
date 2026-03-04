# Presets Reference

Bundled in `odoo_venv/assets/presets.toml` inside the installed package (not an XDG path). Read with `odoo-venv create --preset <name>`.

## Merge semantics

- `[common]` is the base. Every named preset is merged on top of it.
- String fields (e.g., `extra_requirement`, `ignore_from_odoo_requirements`) **concatenate** with commas.
- List fields (e.g., `extra_commands`) **extend**.
- Boolean/scalar fields in the named preset **override** `[common]`.
- CLI flags override all preset values except `--extra-requirement`, which extends.

## Preset option reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `install_odoo` | bool | true | Install Odoo in editable mode (`pip install -e <odoo_dir>`). |
| `install_odoo_requirements` | bool | true | Install Odoo's `requirements.txt`. |
| `ignore_from_odoo_requirements` | str | "" | CSV of packages to skip from Odoo's requirements. |
| `install_addons_dirs_requirements` | bool | false | Install `requirements.txt` files found in every `--addons-path`. |
| `ignore_from_addons_dirs_requirements` | str | "" | CSV of packages to skip from addon-dir requirements. |
| `install_addons_manifests_requirements` | bool | false | Install `external_dependencies.python` from each addon's manifest. |
| `ignore_from_addons_manifests_requirements` | str | "" | CSV of packages to skip from manifest deps. |
| `extra_requirements_file` | str | "" | Path to a pip requirements file (relative to CWD at run time). |
| `extra_requirement` | str | "" | CSV of extra packages. Use `\,` for literal commas inside a version specifier. |
| `extra_commands` | list[table] | [] | Shell commands to run at defined stages. See below. |

## `[common]` (applied to every preset)

```toml
ignore_from_odoo_requirements = """
gevent==21.8.0; sys_platform != 'win32' and python_version == '3.10',
greenlet==1.1.2; sys_platform != 'win32' and python_version == '3.10',
cbor2==5.4.2 ; python_version < '3.12',
urllib3==1.26.5; python_version > '3.9' and python_version < '3.12',
psycopg2==2.7.3.1; sys_platform != 'win32' and python_version < '3.8'
"""

extra_requirement = """
gevent==22.10.2; sys_platform == 'linux' and python_version == '3.10',
greenlet==2.0.2; sys_platform == 'linux' and python_version == '3.10',
urllib3==1.26.14; python_version > '3.9' and python_version < '3.12',
psycopg2==2.8.3; sys_platform != 'win32' and python_version < '3.8',
click-odoo-contrib==1.23.1
"""

ignore_from_addons_dirs_requirements = "azure-identity,mysql,mysqlclient,pymssql,cn2an"
```

Plus three `extra_commands` that pin `setuptools<82` for Odoo 14.0–17.0, pin `setuptools<82` for Odoo >17.0 on Python 3.10, and install `cbor2==5.4.3` for Odoo ≥18 on Python 3.10 (with `UV_NO_BUILD_ISOLATION=1`).

## Named presets

### `local` — generic dev venv (OCA work)

```toml
install_addons_dirs_requirements = true
install_addons_manifests_requirements = true
extra_requirement = "debugpy,ipython,setproctitle,watchdog,jingtrang,websocket-client,coverage,pylint-odoo,astroid,pdfminer.six,fonttools"
```

### `demo` — demo instances (install everything upfront)

```toml
install_addons_dirs_requirements = true
install_addons_manifests_requirements = true
extra_requirement = "pdfminer.six,fonttools"
```

### `project` — project repos, minimal deps

```toml
install_addons_dirs_requirements = false
install_addons_manifests_requirements = false
extra_requirements_file = "./requirements.txt"
extra_requirement = "pdfminer.six,fonttools"
```

### `ci` — test runner

```toml
install_addons_dirs_requirements = true
install_addons_manifests_requirements = true
extra_requirements_file = "./requirements.txt"
extra_requirement = "websocket-client,coverage,pylint,astroid,pdfminer.six,fonttools"
```

## `extra_commands`

Array of tables. Each entry runs a shell command at a given stage, optionally gated by a `when` marker expression.

```toml
[[common.extra_commands]]
command = ["uv", "pip", "install", "setuptools<82.0"]
when = "odoo_version > '13.0' and odoo_version <= '17.0'"
stage = "after_requirements"
env = { UV_NO_BUILD_ISOLATION = "1" }  # optional
```

**Stages**: `after_venv`, `after_requirements`, `after_odoo_install`.

**`when` markers** (custom evaluator, not stock packaging):

- `odoo_version` — e.g., `'13.0'`, `'18.0'`, `'master'` is excluded from numeric comparisons.
- `python_version` — e.g., `'3.10'`.
- Standard PEP 508 markers: `sys_platform`, `platform_system`, etc.

**Operators**: `==`, `!=`, `<=`, `>=`, `<`, `>`, `and`, `or`.

**Precedence**: `and` binds tighter than `or`. **Parentheses are NOT supported.**

Examples:
```
when = "odoo_version <= '13.0'"
when = "odoo_version == '13.0' or odoo_version == '12.0'"
when = "odoo_version <= '13.0' and python_version >= '3.7'"
when = ""  # always runs
```

## Overriding a preset from the CLI

```bash
# Add pylint on top of `local`
odoo-venv create 17.0 --preset local --extra-requirement "pylint"

# Replace the addons_path from the preset (scalar → overrides)
odoo-venv create 17.0 --preset ci --addons-path ./addons

# Skip manifest reqs even though the preset enables them (boolean → overrides)
odoo-venv create 17.0 --preset local --no-install-addons-manifests-requirements
```
