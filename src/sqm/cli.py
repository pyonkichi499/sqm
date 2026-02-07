from __future__ import annotations

import logging
import os
from pathlib import Path

import click
import numpy as np
import yaml

logger = logging.getLogger(__name__)

# Default simulation configuration
DEFAULT_CONFIG: dict[str, str | int] = {
    "dtau": "0.3d0",
    "ds": "0.3d-5",
    "s_end": "1d0",
    "Nsample": 200,
}


@click.group()
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
@click.option("--nsample", type=int, required=True, help="Number of samples")
@click.option("--workers", type=int, default=None, help="Number of parallel workers")
@click.option("--dry-run", is_flag=True, default=False, help="Print plan without executing")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable debug logging")
@click.option("-q", "--quiet", is_flag=True, default=False, help="Suppress non-essential output")
def sweep(
    u: float | None,
    mu: float | None,
    u_start: float | None,
    u_end: float | None,
    u_step: float | None,
    mu_start: float | None,
    mu_end: float | None,
    mu_step: float | None,
    nsample: int,
    workers: int | None,
    dry_run: bool,
    verbose: bool,
    quiet: bool,
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

    # Build sweep parameters
    if has_mu_sweep:
        assert mu_start is not None and mu_end is not None and mu_step is not None
        sweep_values = np.arange(mu_start, mu_end, mu_step)
        sweep_name = "mu"
        fixed_name = "U"
        fixed_value = u if has_fixed_u else 0.0
    else:
        assert u_start is not None and u_end is not None and u_step is not None
        sweep_values = np.arange(u_start, u_end, u_step)
        sweep_name = "U"
        fixed_name = "mu"
        fixed_value = mu if has_fixed_mu else 0.0

    n_points = len(sweep_values)
    max_workers = workers if workers is not None else min(n_points, os.cpu_count() or 1)

    logger.debug(
        "Sweep configuration: %s sweep, %d points, fixed %s=%s, Nsample=%d",
        sweep_name,
        n_points,
        fixed_name,
        fixed_value,
        nsample,
    )

    if dry_run:
        click.echo(f"Dry run: sweep {sweep_name} ({n_points} points)")
        click.echo(f"  Fixed {fixed_name} = {fixed_value}")
        click.echo(f"  Sweep {sweep_name} = {sweep_values.tolist()}")
        click.echo(f"  Nsample = {nsample}")
        click.echo(f"  {max_workers} workers")
        return

    # Actual execution would go here
    click.echo(
        f"Sweep {sweep_name} ({n_points} points), "
        f"fixed {fixed_name}={fixed_value}, "
        f"{max_workers} workers"
    )


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
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)

    click.echo(f"Configuration file created: {output_path}")


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
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    click.echo("Current configuration:")
    for key, value in cfg.items():
        click.echo(f"  {key}: {value}")


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
