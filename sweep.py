"""ローカル並列パラメータスイープ"""
import os

import click
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

from simulate import run_one
from collect import analyze_one, plot_sweep


def run_and_analyze(params):
    U, mu, nsample, outdir = params
    datfile = run_one(U, mu, nsample, outdir)
    mean, err = analyze_one(datfile)
    return U, mu, mean, err


@click.command()
@click.option("--U", "u_val", type=float, default=None,
              help="U固定値 (省略するとUをスイープ)")
@click.option("--mu", type=float, default=None,
              help="mu固定値 (省略するとmuをスイープ)")
@click.option("--start", type=float, default=0, show_default=True,
              help="スイープ開始値")
@click.option("--end", type=float, default=20, show_default=True,
              help="スイープ終了値 (含まない)")
@click.option("--step", type=float, default=2, show_default=True,
              help="スイープ刻み幅")
@click.option("--Nsample", "nsample", type=int, default=200, show_default=True)
@click.option("--outdir", default="output", show_default=True)
def main(u_val, mu, start, end, step, nsample, outdir):
    if u_val is not None and mu is not None:
        raise click.UsageError(
            "U と mu の両方を指定できません。スイープする方を省略してください。")
    if u_val is None and mu is None:
        raise click.UsageError(
            "U と mu のどちらか一方を固定値として指定してください。")

    os.makedirs(outdir, exist_ok=True)
    sweep_values = np.arange(start, end, step)

    if u_val is not None:
        # U固定、muスイープ
        sweep_name = "mu"
        fixed_name, fixed_value = "U", u_val
        param_grid = [(u_val, m, nsample, outdir) for m in sweep_values]
    else:
        # mu固定、Uスイープ
        sweep_name = "U"
        fixed_name, fixed_value = "mu", mu
        param_grid = [(u, mu, nsample, outdir) for u in sweep_values]

    max_workers = min(len(param_grid), os.cpu_count() or 1)
    click.echo(f"Sweep {sweep_name} ({len(sweep_values)} points), "
               f"fixed {fixed_name}={fixed_value}, "
               f"{max_workers} workers")

    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_and_analyze, p): p for p in param_grid}
        for future in as_completed(futures):
            p = futures[future]
            try:
                U_r, mu_r, mean, err = future.result()
                results[(U_r, mu_r)] = (mean, err)
                click.echo(f"U={U_r}, mu={mu_r} completed")
            except Exception as e:
                click.echo(f"U={p[0]}, mu={p[1]} failed: {e}")

    # 結果を集約してプロット
    corr_mean_list = []
    corr_err_list = []
    for v in sweep_values:
        key = (v, fixed_value) if sweep_name == "U" else (fixed_value, v)
        mean, err = results.get(key, (np.nan, 0.0))
        corr_mean_list.append(mean)
        corr_err_list.append(err)

    figname = plot_sweep(
        sweep_values, corr_mean_list, corr_err_list,
        sweep_name, fixed_name, fixed_value, nsample, outdir,
    )
    click.echo(f"Saved {figname}")


if __name__ == "__main__":
    main()
