import re
import subprocess
import sys
from dataclasses import dataclass, fields
from importlib import metadata
from pathlib import Path

import tomli
from packaging.version import Version


def split_escaped(s: str, sep: str = ",") -> list[str]:
    """Split *s* on *sep*, honouring backslash-escaped separators.

    Escaped separators (``\\,``) are preserved as literal characters in the
    resulting items; unescaped separators are used as split points.

    >>> split_escaped("sentry_sdk,requests")
    ['sentry_sdk', 'requests']
    >>> split_escaped(r"sentry_sdk>=2.0.0\\,<=2.22.0")
    ['sentry_sdk>=2.0.0,<=2.22.0']
    >>> split_escaped(r"a,sentry_sdk>=2.0.0\\,<=2.22.0,b")
    ['a', 'sentry_sdk>=2.0.0,<=2.22.0', 'b']
    >>> split_escaped("")
    ['']
    """
    parts = re.split(rf"(?<!\\){re.escape(sep)}", s)
    return [p.replace(f"\\{sep}", sep) for p in parts]


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
    extra_commands: list[dict] | None = None

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


def _merge_preset_options(
    common_options: dict,
    preset_options: dict,
) -> dict:
    """Merge common preset options with a specific preset's options.

    Args:
        common_options: Options from the [common] preset
        preset_options: Options from the specific preset

    Returns:
        Merged options dictionary
    """
    string_list_fields = {
        "ignore_from_odoo_requirements",
        "ignore_from_addons_dirs_requirements",
        "ignore_from_addons_manifests_requirements",
        "extra_requirement",
    }
    list_fields = {"extra_commands"}

    merged_options = {}

    # Apply settings from 'common' preset
    for key, common_value in common_options.items():
        if key != "description" and common_value is not None:
            merged_options[key] = common_value

    # Apply from specific preset
    for key, val in preset_options.items():
        if val is None:
            continue

        if key in list_fields and key in merged_options and merged_options[key]:
            # Extend list fields
            if isinstance(merged_options[key], list) and isinstance(val, list):
                merged_options[key] = merged_options[key] + val
            else:
                merged_options[key] = val
        elif key in string_list_fields and key in merged_options and merged_options[key]:
            merged_options[key] = f"{merged_options[key]},{val}"
        else:
            merged_options[key] = val

    return merged_options


def load_presets() -> dict[str, Preset]:
    with open(USER_PRESETS_PATH, "rb") as f:
        presets_data = tomli.load(f)

    if "common" in presets_data:
        common_options = presets_data["common"]

        for name, options in presets_data.items():
            # Skip processing 'common' - it's already in the right format
            if name == "common":
                continue

            presets_data[name] = _merge_preset_options(common_options, options)

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
