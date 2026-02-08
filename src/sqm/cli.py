from __future__ import annotations

import logging
import os
from pathlib import Path

import click

from sqm.config import Config, PathConfig, SimulationConfig, SweepConfig
from sqm.runner import run_sweep

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0", prog_name="sqm")
def cli() -> None:
    """SQM: Complex Langevin simulation for Bose-Hubbard model"""
    pass


@cli.command()
@click.option("--u", type=float, default=None, help="Fixed U value")
@click.option("--mu", type=float, default=None, help="Fixed mu value")
@click.option("--u-start", type=float, default=None, help="U sweep start")
@click.option("--u-end", type=float, default=None, help="U sweep end")
@click.option("--u-step", type=float, default=None, help="U sweep step")
@click.option("--mu-start", type=float, default=None, help="mu sweep start")
@click.option("--mu-end", type=float, default=None, help="mu sweep end")
@click.option("--mu-step", type=float, default=None, help="mu sweep step")
@click.option(
    "--nsample", type=int, default=None, help="Number of samples (uses config default if omitted)"
)
@click.option("--workers", type=int, default=None, help="Number of parallel workers")
@click.option("--dry-run", is_flag=True, default=False, help="Print plan without executing")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable debug logging")
@click.option("-q", "--quiet", is_flag=True, default=False, help="Suppress non-essential output")
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to YAML config file",
)
@click.option(
    "--skip-autocorrelation",
    is_flag=True,
    default=False,
    help="Skip autocorrelation analysis",
)
@click.option(
    "-o",
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Override output directory",
)
@click.option(
    "--figures-dir",
    type=click.Path(),
    default=None,
    help="Override figures directory",
)
@click.option(
    "--fortran-binary",
    type=click.Path(),
    default=None,
    help="Override Fortran binary path",
)
@click.option(
    "--s-end",
    type=str,
    default=None,
    help="Override simulation virtual time (Fortran literal, e.g. '0.01d0')",
)
def sweep(
    u: float | None,
    mu: float | None,
    u_start: float | None,
    u_end: float | None,
    u_step: float | None,
    mu_start: float | None,
    mu_end: float | None,
    mu_step: float | None,
    nsample: int | None,
    workers: int | None,
    dry_run: bool,
    verbose: bool,
    quiet: bool,
    config_path: str | None,
    skip_autocorrelation: bool,
    output_dir: str | None,
    figures_dir: str | None,
    fortran_binary: str | None,
    s_end: str | None,
) -> None:
    """Run a parameter sweep over U or mu."""
    _configure_logging(verbose=verbose, quiet=quiet)

    # Determine sweep mode
    has_mu_sweep = mu_start is not None and mu_end is not None and mu_step is not None
    has_u_sweep = u_start is not None and u_end is not None and u_step is not None
    has_fixed_u = u is not None
    has_fixed_mu = mu is not None

    # Validate: exactly one of U or mu must be swept
    if has_fixed_u and has_fixed_mu:
        raise click.UsageError("Cannot fix both --u and --mu. One must be swept.")

    if has_mu_sweep and has_u_sweep:
        raise click.UsageError("Cannot sweep both mu and U simultaneously.")

    if has_mu_sweep and has_fixed_mu:
        raise click.UsageError("Cannot specify both --mu (fixed) and --mu-start/end/step (sweep).")

    if has_u_sweep and has_fixed_u:
        raise click.UsageError("Cannot specify both --u (fixed) and --u-start/end/step (sweep).")

    if not has_mu_sweep and not has_u_sweep:
        raise click.UsageError(
            "Must specify a sweep range: either --mu-start/--mu-end/--mu-step "
            "or --u-start/--u-end/--u-step."
        )

    # Build Config (needed for both dry-run and execution)
    config_obj = _build_config(
        config_path=config_path,
        u=u,
        mu=mu,
        u_start=u_start,
        u_end=u_end,
        u_step=u_step,
        mu_start=mu_start,
        mu_end=mu_end,
        mu_step=mu_step,
        nsample=nsample,
        output_dir=output_dir,
        figures_dir=figures_dir,
        fortran_binary=fortran_binary,
        s_end=s_end,
    )

    sweep_cfg = config_obj.sweep
    assert sweep_cfg is not None
    sweep_values_list = sweep_cfg.sweep_values()
    sweep_name = sweep_cfg.sweep_param

    if sweep_name == "mu":
        fixed_name = "U"
        fixed_value = u if has_fixed_u else 0.0
    else:
        fixed_name = "mu"
        fixed_value = mu if has_fixed_mu else 0.0

    n_points = len(sweep_values_list)
    max_workers = workers if workers is not None else min(n_points, os.cpu_count() or 1)

    effective_nsample = config_obj.simulation.Nsample

    logger.debug(
        "Sweep configuration: %s sweep, %d points, fixed %s=%s, Nsample=%d",
        sweep_name,
        n_points,
        fixed_name,
        fixed_value,
        effective_nsample,
    )

    if dry_run:
        click.echo(f"Dry run: sweep {sweep_name} ({n_points} points)")
        click.echo(f"  Fixed {fixed_name} = {fixed_value}")
        click.echo(f"  Sweep {sweep_name} = {sweep_values_list}")
        click.echo(f"  Nsample = {effective_nsample}")
        click.echo(f"  {max_workers} workers")
        return

    click.echo(
        f"Sweep {sweep_name} ({n_points} points), "
        f"fixed {fixed_name}={fixed_value}, "
        f"{max_workers} workers"
    )

    result = run_sweep(
        config_obj,
        skip_autocorrelation=skip_autocorrelation,
        max_workers=max_workers,
    )

    # サマリー表示
    click.echo(f"\n完了: {len(result.points)} 成功, {len(result.failed)} 失敗")
    click.echo(f"実行時間: {result.walltime_seconds:.1f} 秒")
    click.echo(f"出力ディレクトリ: {result.config.paths.output_dir}")
    click.echo(f"グラフ: {result.config.paths.figures_dir}")
    if result.failed:
        click.echo("失敗ポイント:")
        for fu, fmu, msg in result.failed:
            click.echo(f"  U={fu}, mu={fmu}: {msg}")


@cli.group()
def config() -> None:
    """Manage simulation configuration files."""
    pass


@config.command("init")
@click.option(
    "--output",
    type=click.Path(),
    default="config.yaml",
    help="Output path for the configuration file",
)
def config_init(output: str) -> None:
    """Generate a default configuration file."""
    cfg = Config()
    cfg.to_yaml(Path(output))
    click.echo(f"Configuration file created: {output}")


@config.command("show")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True),
    default="config.yaml",
    help="Path to the configuration file",
)
def config_show(config_path: str) -> None:
    """Show the current configuration."""
    cfg = Config.from_yaml(Path(config_path))
    click.echo("Current configuration:")
    click.echo("  simulation:")
    click.echo(f"    dtau: {cfg.simulation.dtau}")
    click.echo(f"    ds: {cfg.simulation.ds}")
    click.echo(f"    s_end: {cfg.simulation.s_end}")
    click.echo(f"    Nsample: {cfg.simulation.Nsample}")
    click.echo("  paths:")
    click.echo(f"    output_dir: {cfg.paths.output_dir}")
    click.echo(f"    figures_dir: {cfg.paths.figures_dir}")
    click.echo(f"    fortran_binary: {cfg.paths.fortran_binary}")
    click.echo("  seed:")
    click.echo(f"    mode: {cfg.seed.mode}")
    click.echo(f"    base_seed: {cfg.seed.base_seed}")


def _build_config(
    *,
    config_path: str | None,
    u: float | None,
    mu: float | None,
    u_start: float | None,
    u_end: float | None,
    u_step: float | None,
    mu_start: float | None,
    mu_end: float | None,
    mu_step: float | None,
    nsample: int | None,
    output_dir: str | None,
    figures_dir: str | None,
    fortran_binary: str | None,
    s_end: str | None = None,
) -> Config:
    """CLI引数とオプションのconfigファイルから Config を構築する。"""
    # Base config: from file or defaults
    base_config = Config.from_yaml(Path(config_path)) if config_path is not None else Config()

    # Nsample: CLI引数優先、なければconfigから取得
    effective_nsample = nsample if nsample is not None else base_config.simulation.Nsample

    # Simulation settings
    sim = SimulationConfig(
        dtau=base_config.simulation.dtau,
        ds=base_config.simulation.ds,
        s_end=s_end if s_end is not None else base_config.simulation.s_end,
        Nsample=effective_nsample,
    )

    # Path settings (CLI overrides)
    paths = PathConfig(
        output_dir=Path(output_dir) if output_dir else base_config.paths.output_dir,
        figures_dir=Path(figures_dir) if figures_dir else base_config.paths.figures_dir,
        fortran_binary=(
            Path(fortran_binary) if fortran_binary else base_config.paths.fortran_binary
        ),
    )

    # Sweep settings
    sweep_cfg = SweepConfig(
        U=u,
        mu=mu,
        mu_start=mu_start,
        mu_end=mu_end,
        mu_step=mu_step,
        U_start=u_start,
        U_end=u_end,
        U_step=u_step,
    )

    return Config(
        simulation=sim,
        paths=paths,
        sweep=sweep_cfg,
        seed=base_config.seed,
    )


def _configure_logging(*, verbose: bool, quiet: bool) -> None:
    """Configure logging level based on verbosity flags."""
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )
    logger.setLevel(level)


if __name__ == "__main__":
    cli()
