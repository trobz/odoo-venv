from dataclasses import dataclass
from pathlib import Path

import tomli

MODULE_PATH = Path(__file__).parent
DEFAULT_MODES_PATH = MODULE_PATH / "assets" / "modes.toml"


def _ensure_list(value) -> list[str]:
    """Normalize a TOML value to a list of strings.

    Accepts a single string or a list of strings.
    """
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return value
    return []


@dataclass
class ModeOverride:
    package: str
    ignore: list[str]
    install: list[str]
    when: str = ""
    reason: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ModeOverride":
        return cls(
            package=data.get("package", ""),
            ignore=_ensure_list(data.get("ignore", [])),
            install=_ensure_list(data.get("install", [])),
            when=data.get("when", ""),
            reason=data.get("reason", ""),
        )


@dataclass
class KnownIssue:
    package: str
    error_pattern: str
    suggestion: str
    link: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "KnownIssue":
        return cls(
            package=data.get("package", ""),
            error_pattern=data.get("error_pattern", ""),
            suggestion=data.get("suggestion", ""),
            link=data.get("link", ""),
        )


@dataclass
class Mode:
    description: str
    strategy: str  # "compat" | "latest-secure" | "uncapped"
    overrides: list[ModeOverride]
    known_issues: list[KnownIssue]
    extra_commands: list[dict]


def load_modes(path: Path | None = None) -> dict[str, Mode]:
    """Load modes from modes.toml. Modern inherits conservative overrides."""
    path = path or DEFAULT_MODES_PATH
    with open(path, "rb") as f:
        data = tomli.load(f)

    modes: dict[str, Mode] = {}
    for name, mode_data in data.items():
        overrides = [ModeOverride.from_dict(o) for o in mode_data.get("overrides", [])]
        known_issues = [KnownIssue.from_dict(k) for k in mode_data.get("known_issues", [])]
        extra_commands = mode_data.get("extra_commands", [])
        modes[name] = Mode(
            description=mode_data.get("description", ""),
            strategy=mode_data.get("strategy", "compat"),
            overrides=overrides,
            known_issues=known_issues,
            extra_commands=extra_commands,
        )

    # Resolve inheritance: modern = conservative overrides + modern-specific
    # Dedup by package name: modern's version wins (last-write) for same package
    if "conservative" in modes and "modern" in modes:
        modern = modes["modern"]
        conservative = modes["conservative"]
        modern_pkg_names = {o.package for o in modern.overrides}
        inherited = [o for o in conservative.overrides if o.package not in modern_pkg_names]
        modern.overrides = inherited + modern.overrides
        modern.known_issues = conservative.known_issues + modern.known_issues
        modern.extra_commands = conservative.extra_commands + modern.extra_commands

    return modes
