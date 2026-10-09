from pathlib import Path

from typer import BadParameter


class PresetNotFoundError(BadParameter):
    def __init__(self, preset: str) -> None:
        super().__init__(f"Preset '{preset}' not found.")


class OdooVenvError(Exception):
    """General error raised by ovx operations."""


class AddonPathNotADirectoryError(OdooVenvError):
    def __init__(self, addon_path: Path) -> None:
        super().__init__(f"Addon path is not a directory: {addon_path}")


class ManifestNotFoundError(OdooVenvError):
    def __init__(self, addon_path: Path) -> None:
        super().__init__(f"Missing __manifest__.py in {addon_path}")


class VenvConfigNotFoundError(OdooVenvError):
    def __init__(self, venv_dir: Path) -> None:
        super().__init__(f"No .odoo-venv.toml recorded at {venv_dir}; cannot determine its Odoo series.")


class ResolvedVenvPathMissingError(OdooVenvError):
    def __init__(self) -> None:
        super().__init__("Internal error: resolved venv path is None")


class OdooVersionUndeterminedError(OdooVenvError):
    def __init__(self, odoo_dir: Path) -> None:
        super().__init__(f"Could not determine the Odoo version from --odoo-dir {odoo_dir}")


class VenvCreationRequiresOdooDirError(OdooVenvError):
    def __init__(self, venv_dir: Path) -> None:
        super().__init__(f"Cannot create a venv at {venv_dir} without --odoo-dir")


class ConflictingOdooSeriesError(OdooVenvError):
    def __init__(self, participants: list[tuple[str, str | None]]) -> None:
        lines = "\n".join(f"  {label}: {s if s is not None else '(no declared series)'}" for label, s in participants)
        super().__init__(
            f"conflicting Odoo series.\n{lines}\n"
            "All sources must agree. Pass addons for a single series, or a matching --venv-dir/--odoo-dir."
        )


class OdooSeriesUndeterminedError(OdooVenvError):
    def __init__(self) -> None:
        super().__init__(
            "Cannot determine the Odoo series: pass --odoo-dir or --venv-dir, "
            "or ensure at least one addon declares a version."
        )


class EmptyAddonPathEntryError(BadParameter):
    def __init__(self) -> None:
        super().__init__("Empty path entry in comma-separated addon_paths.", param_hint="addon_paths")
