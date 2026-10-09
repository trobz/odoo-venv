"""Venv resolution and clone primitives for the ovx command."""

import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from odoo_addons_path import get_odoo_version_from_manifest

from odoo_venv.exceptions import AddonPathNotADirectoryError, ManifestNotFoundError, VenvConfigNotFoundError
from odoo_venv.main import _freeze_venv
from odoo_venv.utils import read_venv_config


@dataclass
class ResolvedVenv:
    path: Path | None
    fresh: bool
    source: Literal["explicit", "fresh"]


def get_addon_series(addon_path: Path) -> str | None:
    """Return the Odoo major series (e.g. '19.0') for the given addon directory, or None if undeclared."""
    if not addon_path.is_dir():
        raise AddonPathNotADirectoryError(addon_path)
    manifest_file = addon_path / "__manifest__.py"
    if not manifest_file.is_file():
        raise ManifestNotFoundError(addon_path)
    return get_odoo_version_from_manifest(manifest_file)


def read_venv_meta(venv_dir: Path) -> dict[str, str]:
    """Read the recorded venv metadata from .odoo-venv.toml, raising an actionable error if absent."""
    try:
        _, meta, _, _ = read_venv_config(venv_dir)
    except FileNotFoundError:
        raise VenvConfigNotFoundError(venv_dir) from None
    return meta


def resolve_base_venv(
    *,
    venv_dir: Path | None,
    odoo_dir: Path | None,
) -> ResolvedVenv:
    """Resolve the base venv to use for an ovx run.

    The series disagreement check happens upstream in `_resolve_series`; by the time this
    function runs, `venv_dir` (if given) is already known to agree with every other source.
    """
    if venv_dir is not None and venv_dir.exists():
        return ResolvedVenv(path=venv_dir, fresh=False, source="explicit")

    # No existing explicit venv: fresh-create. odoo_dir is guaranteed not None here when
    # venv_dir is also None, because the CLI enforces at least one of the two flags.
    return ResolvedVenv(path=None, fresh=True, source="fresh")


def clone_venv(base: Path) -> tuple[Path, "Callable[[], None]"]:
    """Clone *base* venv into a temporary directory.

    Returns ``(clone_path, cleanup_fn)``. The caller must call ``cleanup_fn()``
    when done (analogous to TemporaryDirectory.__exit__).
    """
    tmpdir = tempfile.mkdtemp(prefix="ovx_clone_")
    clone = Path(tmpdir) / base.name

    # Try copy-on-write first (fast on btrfs/apfs), then plain copy.
    # We do NOT use -l (hard links) because mutating the clone would mutate the base.
    result = subprocess.run(  # noqa: S603
        ["cp", "--reflink=auto", "-r", str(base), str(clone)],  # noqa: S607
        capture_output=True,
    )
    if result.returncode != 0:
        shutil.copytree(base, clone, symlinks=True)

    _patch_pyvenv_cfg(clone, base)

    def cleanup():
        shutil.rmtree(tmpdir, ignore_errors=True)

    return clone, cleanup


def _patch_pyvenv_cfg(clone: Path, base: Path) -> None:
    """Rewrite pyvenv.cfg in the clone so it no longer references the base path."""
    cfg = clone / "pyvenv.cfg"
    if not cfg.exists():
        return
    text = cfg.read_text()
    # Replace the prompt so it reflects the clone name, not the base name
    text = text.replace(f"prompt = {base.name}", f"prompt = {clone.name}")
    cfg.write_text(text)


def install_missing_python_deps(clone: Path, manifest: dict) -> list[str]:
    """Install any python external_dependencies missing from the clone venv.

    Returns the list of packages that were actually installed.
    """
    deps: list[str] = manifest.get("external_dependencies", {}).get("python", [])
    if not deps:
        return []

    installed = _freeze_venv(clone)
    missing = [dep for dep in deps if re.sub(r"[-_.]+", "-", dep).lower() not in installed]
    if not missing:
        return []

    subprocess.run(  # noqa: S603
        ["uv", "pip", "install", "--python", str(clone), *missing],  # noqa: S607
        check=True,
    )
    return missing
