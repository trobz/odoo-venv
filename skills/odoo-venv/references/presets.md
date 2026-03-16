# Presets Configuration

Presets defined in `~/.local/share/odoo-venv/presets.toml`.

## Available Presets

### local (Development)

For generic local development, includes dev tools.

```toml
install_addons_dirs_requirements = true
install_addons_manifests_requirements = true
extra_requirement = "debugpy,ipython,setproctitle,watchdog,jingtrang,websocket-client,coverage,pylint-odoo,astroid,pdfminer.six,fonttools"
```

### demo

For demo instances, installs all module requirements upfront.

```toml
install_addons_dirs_requirements = true
install_addons_manifests_requirements = true
extra_requirement = "pdfminer.six,fonttools"
```

### project

For projects (dev/staging/production), minimal dependencies.

```toml
install_addons_dirs_requirements = false
install_addons_manifests_requirements = false
extra_requirements_file = "./requirements.txt"
extra_requirement = "pdfminer.six,fonttools"
```

### ci (Testing)

For CI/testing environments.

```toml
install_addons_dirs_requirements = true
install_addons_manifests_requirements = true
extra_requirements_file = "./requirements.txt"
extra_requirement = "websocket-client,coverage,pylint,astroid,pdfminer.six,fonttools"
```

## Common Configuration

Applied to all presets. Fixes gevent issues on Ubuntu 22.04/24.04:

```toml
[common]
ignore_from_odoo_requirements = "gevent==21.8.0..., greenlet==1.1.2..."
extra_requirement = "gevent==22.10.2..., greenlet==2.0.2..."
ignore_from_addons_dirs_requirements = "azure-identity,mysql,mysqlclient,pymssql,cn2an"
```

## Preset Options Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `install_odoo` | bool | true | Install Odoo in editable mode |
| `install_odoo_requirements` | bool | true | Install from Odoo's requirements.txt |
| `ignore_from_odoo_requirements` | str | "" | Packages to skip from Odoo requirements |
| `install_addons_dirs_requirements` | bool | false | Install requirements.txt from addon paths |
| `ignore_from_addons_dirs_requirements` | str | "" | Packages to skip from addon requirements |
| `install_addons_manifests_requirements` | bool | false | Install from addon manifests |
| `ignore_from_addons_manifests_requirements` | str | "" | Packages to skip from manifests |
| `extra_requirements_file` | str | "" | Path to extra requirements file |
| `extra_requirement` | str | "" | Comma-separated extra packages |

## Override Preset Values

```bash
odoo-venv create 17.0 --preset demo --extra-requirement "pylint"
```
