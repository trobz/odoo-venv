"""Launcher script generation for Odoo environments."""

import os
import sys
from pathlib import Path
from string import Template

import typer

LAUNCHER_DIR = Path("~/.local/bin").expanduser()
TEMPLATE_PATH = Path(__file__).parent / "assets" / "launcher.sh.template"


def create_launcher(
    odoo_version: str,
    venv_dir: str | Path,
    force: bool = False,
    project_dir: str | None = None,
    odoo_dir: str | None = None,
    name: str | None = None,
) -> Path:
    """
    Generate a bash launcher script that auto-activates the venv and runs Odoo.

    Args:
        odoo_version: Odoo version string (e.g., "19.0")
        venv_dir: Path to the virtual environment
        force: Overwrite existing launcher if True
        project_dir: Path to project directory; when set, the launcher will
            run ``odoo-addons-path`` at startup to resolve addons paths
            dynamically (unless ADDONS_PATH is explicitly configured).
        odoo_dir: Path to Odoo source directory; passed to ``odoo-addons-path``
            via ``--odoo-dir`` so the base Odoo addons are included.
        name: Custom launcher script name. When provided, the script is named
            ``odoo-v{major}-{name}`` instead of the default ``odoo-v{major}``.

    Returns:
        Path to the created launcher script

    Raises:
        SystemExit: If file exists and force=False, or on write errors
    """
    major_version = odoo_version.split(".")[0]
    script_name = f"odoo-v{major_version}-{name}" if name else f"odoo-v{major_version}"
    output_path = LAUNCHER_DIR / script_name

    # Resolve venv path to absolute
    venv_path = Path(venv_dir).expanduser().resolve()

    # Check if file exists
    if output_path.exists() and not force:
        typer.secho(
            f"Launcher script already exists: {output_path}\nUse --force to overwrite.",
            fg=typer.colors.YELLOW,
        )
        return output_path

    # Create output directory if needed
    LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)

    # Read and render template
    try:
        template_content = TEMPLATE_PATH.read_text()
        rendered = Template(template_content).substitute(
            VENV_DIR=str(venv_path),
            PROJECT_DIR=project_dir or "",
            ODOO_DIR=odoo_dir or "",
        )
    except FileNotFoundError:
        typer.secho(f"Template not found: {TEMPLATE_PATH}", fg=typer.colors.RED, err=True)
        sys.exit(1)
    except (KeyError, ValueError) as e:
        typer.secho(f"Template substitution failed: {e}", fg=typer.colors.RED, err=True)
        sys.exit(1)

    # Security: Check for symlink before writing
    if output_path.is_symlink():
        typer.secho(
            f"Error: {output_path} is a symbolic link. Refusing to overwrite for security reasons.",
            fg=typer.colors.RED,
            err=True,
        )
        sys.exit(1)

    # Write script
    try:
        output_path.write_text(rendered)
        output_path.chmod(0o755)
    except PermissionError:
        typer.secho(
            f"Permission denied writing to {output_path}\nEnsure you have write access to {LAUNCHER_DIR}",
            fg=typer.colors.RED,
            err=True,
        )
        sys.exit(1)

    # Check if launcher dir is in PATH
    if str(LAUNCHER_DIR) not in os.environ.get("PATH", ""):
        typer.secho(
            f"\nWarning: {LAUNCHER_DIR} is not in your PATH.\n"
            f"Add this to your shell profile (~/.bashrc or ~/.zshrc):\n"
            f'  export PATH="$PATH:{LAUNCHER_DIR}"',
            fg=typer.colors.YELLOW,
        )

    typer.secho(f"✓ Launcher created: {output_path}", fg=typer.colors.GREEN)
    return output_path
