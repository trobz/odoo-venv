import subprocess
import sys
from dataclasses import dataclass, fields
from importlib import metadata
from pathlib import Path

import tomli
from packaging.version import Version

ROOT_PATH = Path("~/.local/share/odoo-venv/").expanduser()
PRESETS_FILE = "presets.toml"
MODULE_PATH = Path(__file__).parent

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@dataclass
class Preset:
    install_odoo: bool | None = True
    install_odoo_requirements: bool | None = True
    ignore_from_odoo_requirements: str | None = None
    install_addons_dirs_requirements: bool | None = False
    ignore_from_addons_dirs_requirements: str | None = None
    install_addons_manifests_requirements: bool | None = False
    ignore_from_addons_manifests_requirements: str | None = None
    extra_requirements_file: str | None = None
    extra_requirement: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Preset":
        valid_fields = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**data)


def initialize_presets():
    if not ROOT_PATH.exists():
        ROOT_PATH.mkdir(parents=True)

    user_presets_path = ROOT_PATH / PRESETS_FILE
    if not user_presets_path.exists():
        default_presets_path = MODULE_PATH / "assets" / PRESETS_FILE
        # copy default presets and store in root_path
        user_presets_path.write_text(default_presets_path.read_text())


def load_presets() -> dict[str, Preset]:
    default_presets_path = MODULE_PATH / "assets" / PRESETS_FILE
    with open(default_presets_path, "rb") as f:
        presets_data = tomli.load(f)

    user_presets_path = ROOT_PATH / PRESETS_FILE
    if user_presets_path.exists():
        with open(user_presets_path, "rb") as f:
            user_presets = tomli.load(f)
            for preset_name, options in user_presets.items():
                if preset_name in presets_data:
                    presets_data[preset_name].update(options)
                else:
                    presets_data[preset_name] = options

    return {name: Preset.from_dict(options) for name, options in presets_data.items()}


def run_migration():
    app_version = metadata.version("odoo-venv")
    version_file = ROOT_PATH / "version"
    if not version_file.exists():
        version_file.write_text("0.1.0")
    last_version = version_file.read_text().strip()

    if Version(app_version) <= Version(last_version):
        return

    migration_scripts = sorted(
        MIGRATIONS_DIR.glob("*.py"),
        key=lambda x: Version(x.stem.replace("_", ".")),
    )

    for script in migration_scripts:
        version_str = script.stem.replace("_", ".")
        if Version(version_str) > Version(last_version):
            subprocess.run(  # noqa: S603
                [sys.executable, str(script)],
                check=True,
                capture_output=True,
                text=True,
            )

    version_file.write_text(app_version)
