from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from odoo_venv.exceptions import PresetNotFoundError
from odoo_venv.main import create_odoo_venv
from odoo_venv.utils import initialize_presets, load_presets, run_migration

app = typer.Typer()
initialize_presets()
run_migration()
# we use same python versions as OCA: https://github.com/oca/oca-ci/blob/master/.github/workflows/ci.yaml
# with some adjustments based on our experience
# we don't define a specific minor version here, but can be done via --python-version=
ODOO_PYTHON_VERSIONS = {
    "12.0": "3.7",  # faced issues with gevent and python 3.6
    "13.0": "3.7",
    "14.0": "3.8",
    "15.0": "3.8",
    "16.0": "3.10",
    "17.0": "3.10",
    "18.0": "3.10",
    "19.0": "3.10",
}


def preset_callback(ctx: typer.Context, param: typer.CallbackParam, value: str):
    if not value:
        return None

    all_presets = load_presets()
    if value not in all_presets:
        raise PresetNotFoundError(value)

    preset_vals = all_presets[value]
    preset_options = asdict(preset_vals)

    ctx.default_map = ctx.default_map or {}
    ctx.default_map.update(preset_options)
    if descr := preset_options["description"]:
        typer.secho(f"Applying preset '{value}': {descr}", fg=typer.colors.GREEN)
    return value


@app.command()
def create(
    ctx: typer.Context,
    odoo_version: Annotated[str, typer.Argument(help="Odoo version, e.g: 18.0")],
    python_version: Annotated[
        str | None,
        typer.Option("--python-version", "-p", help="Specify Python version."),
    ] = None,
    venv_dir: Annotated[str, typer.Option(help="Path to create the virtual environment.")] = "./.venv",
    odoo_dir: Annotated[str | None, typer.Option(help="Path to Odoo source code.")] = None,
    addons_path: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of addons paths."),
    ] = None,
    install_odoo: Annotated[
        bool,
        typer.Option(
            help="Install Odoo in editable mode.",
        ),
    ] = True,
    install_odoo_requirements: Annotated[
        bool,
        typer.Option(
            help="Install packages from Odoo's requirement.txt.",
        ),
    ] = True,
    ignore_from_odoo_requirements: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of packages to ignore from Odoo's requirement.txt."),
    ] = None,
    install_addons_dirs_requirements: Annotated[
        bool,
        typer.Option(
            help="Install requirements.txt found in addons paths.",
        ),
    ] = False,
    ignore_from_addons_dirs_requirements: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of packages to ignore from addons paths' requirement.txt."),
    ] = None,
    install_addons_manifests_requirements: Annotated[
        bool,
        typer.Option(
            help="Install requirements from addons' manifests.",
        ),
    ] = False,
    ignore_from_addons_manifests_requirements: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of packages to ignore from addons' manifests."),
    ] = None,
    extra_requirements_file: Annotated[
        str | None,
        typer.Option(
            help="Path to an extra requirements file.",
        ),
    ] = None,
    extra_requirement: Annotated[
        str | None,
        typer.Option(help="Comma-separated list of extra packages to install."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(help="Display more details to user"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(),
    ] = False,
    preset: Annotated[
        str | None,
        typer.Option(
            "--preset",
            callback=preset_callback,
            is_eager=True,  # tell Typer to process this first
            help="Use a preset of options. Preset values can be overriden by other options.",
        ),
    ] = None,
):
    """Create virtual environment to run Odoo"""
    if not odoo_dir:
        odoo_dir_path = Path(f"~/code/odoo/odoo/{odoo_version}").expanduser()
    else:
        odoo_dir_path = Path(odoo_dir).expanduser().resolve()

    if not python_version:
        python_version = ODOO_PYTHON_VERSIONS.get(odoo_version)

    venv_dir_path = Path(venv_dir).expanduser().resolve()

    extra_requirements_list = []
    if extra_requirement:
        if isinstance(extra_requirement, str):
            extra_requirements_list = extra_requirement.split(",")
        else:
            extra_requirements_list = list(extra_requirement)

    addons_path_list = (
        [str(Path(p.strip()).expanduser().resolve()) for p in addons_path.split(",")] if addons_path else None
    )

    create_odoo_venv(
        odoo_version=odoo_version,
        odoo_dir=str(odoo_dir_path),
        venv_dir=str(venv_dir_path),
        python_version=python_version,
        install_odoo=install_odoo,
        install_odoo_requirements=install_odoo_requirements,
        ignore_from_odoo_requirements=ignore_from_odoo_requirements,
        addons_paths=addons_path_list,
        install_addons_dirs_requirements=install_addons_dirs_requirements,
        ignore_from_addons_dirs_requirements=ignore_from_addons_dirs_requirements,
        install_addons_manifests_requirements=install_addons_manifests_requirements,
        ignore_from_addons_manifests_requirements=ignore_from_addons_manifests_requirements,
        extra_requirements_file=extra_requirements_file,
        extra_requirements=extra_requirements_list,
        verbose=verbose,
        dry_run=dry_run,
    )
