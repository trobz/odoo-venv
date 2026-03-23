import re
from dataclasses import dataclass, fields
from pathlib import Path

import tomli


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


MODULE_PATH = Path(__file__).parent
DEFAULT_PRESETS_PATH = MODULE_PATH / "assets" / "presets.toml"


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
    with open(DEFAULT_PRESETS_PATH, "rb") as f:
        presets_data = tomli.load(f)

    if "common" in presets_data:
        common_options = presets_data["common"]

        for name, options in presets_data.items():
            # Skip processing 'common' - it's already in the right format
            if name == "common":
                continue

            presets_data[name] = _merge_preset_options(common_options, options)

    return {name: Preset.from_dict(options) for name, options in presets_data.items()}
