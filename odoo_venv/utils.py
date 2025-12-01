from dataclasses import dataclass, fields
from pathlib import Path

import tomli

ROOT_PATH = Path("~/.local/share/odoo-venv/").expanduser()
PRESETS_FILE = "presets.toml"
MODULE_PATH = Path(__file__).parent


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
