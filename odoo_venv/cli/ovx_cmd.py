"""Standalone CLI entry point for the `ovx` command."""

from pathlib import Path
from typing import Annotated

import typer

from odoo_venv.exceptions import OdooVenvError
from odoo_venv.ovx import run_ovx

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def main(
    ctx: typer.Context,
    addon_paths: Annotated[
        str,
        typer.Argument(help="Comma-separated paths to Odoo addon directories (e.g. ./a,~/oca/b)."),
    ],
    venv_dir: Annotated[
        Path | None,
        typer.Option("--venv-dir", help="Explicit venv to use (must match addon's Odoo series)."),
    ] = None,
    odoo_dir: Annotated[
        Path | None,
        typer.Option("--odoo-dir", help="Odoo source directory (required when creating a fresh venv)."),
    ] = None,
    database: Annotated[
        str | None,
        typer.Option("-d", "--database", help="Named DB to use. Suppresses ephemeral DB creation and cleanup."),
    ] = None,
    keep_clone: Annotated[
        bool,
        typer.Option("--keep-clone", hidden=True, help="Keep the cloned venv on disk after run."),
    ] = False,
    no_launcher: Annotated[
        bool,
        typer.Option("--no-launcher", help="Skip launcher script creation."),
    ] = False,
    addons_path: Annotated[
        str | None,
        typer.Option(
            "--addons-path", help="Extra addons paths (comma-separated) for modules the target addon depends on."
        ),
    ] = None,
):
    """Run an Odoo addon on-the-fly — like npx/uvx but for Odoo.

    Detects the addon's Odoo series from __manifest__.py, resolves or creates
    a matching venv, installs missing Python dependencies, then runs Odoo with
    `-i <module>`. The database is ephemeral by default (dropped on exit); pass
    -d <name> to use a named, persistent database.

    Multiple addons can be passed as a comma-separated list (e.g. ./a,~/oca/b).
    The first addon's manifest decides the Odoo series; mismatched modules will
    fail at Odoo's module-not-found error. Paths containing commas are not supported.

    Extra arguments after -- are forwarded verbatim to Odoo.
    """
    parts = [p.strip() for p in addon_paths.split(",")]
    if any(not p for p in parts):
        raise typer.BadParameter("Empty path entry in comma-separated addon_paths.", param_hint="addon_paths")  # noqa: TRY003
    resolved_paths = [Path(p).expanduser().resolve() for p in parts]

    extra_addons: list[str] = []
    if addons_path:
        extra_addons = [str(Path(p.strip()).expanduser().resolve()) for p in addons_path.split(",") if p.strip()]
    try:
        rc = run_ovx(
            resolved_paths,
            venv_dir=venv_dir,
            odoo_dir=odoo_dir,
            database=database,
            keep_clone=keep_clone,
            no_launcher=no_launcher,
            extra_args=ctx.args,
            cwd=Path.cwd(),
            addons_path=extra_addons,
        )
        raise typer.Exit(rc)
    except OdooVenvError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
