import subprocess
import sys
from dataclasses import dataclass, fields
from importlib import metadata
from pathlib import Path

import tomli
from packaging.version import Version

ROOT_PATH = Path("~/.local/share/odoo-venv/").expanduser()
PRESETS_FILE = "presets.toml"
USER_PRESETS_PATH = ROOT_PATH / PRESETS_FILE
MODULE_PATH = Path(__file__).parent
DEFAULT_PRESETS_PATH = MODULE_PATH / "assets" / PRESETS_FILE

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@dataclass
class Preset:
    description: str | None = None
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

    if not USER_PRESETS_PATH.exists():
        # copy default presets and store in root_path
        USER_PRESETS_PATH.write_text(DEFAULT_PRESETS_PATH.read_text())


def load_presets() -> dict[str, Preset]:
    with open(USER_PRESETS_PATH, "rb") as f:
        presets_data = tomli.load(f)

    if "common" in presets_data:
        common_options = presets_data["common"]
        string_list_fields = {
            "ignore_from_odoo_requirements",
            "ignore_from_addons_dirs_requirements",
            "ignore_from_addons_manifests_requirements",
            "extra_requirement",
        }

        for name, options in presets_data.items():
            merged_options = {}

            # apply settings from 'common' preset
            for key, common_value in common_options.items():
                if key != "description" and common_value is not None:
                    merged_options[key] = common_value

            # apply from specific preset
            for key, val in options.items():
                if val is None:
                    continue

                if key in string_list_fields and key in merged_options and merged_options[key]:
                    merged_options[key] = f"{merged_options[key]},{val}"
                else:
                    merged_options[key] = val

            presets_data[name] = merged_options

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
