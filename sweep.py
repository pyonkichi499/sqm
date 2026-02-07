"""ローカル並列パラメータスイープ"""
import os
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

from simulate import run_one
from collect import analyze_one, plot_sweep

# === 設定 ===
# 片方を固定値(スカラー)、もう片方をスイープ範囲(配列)で指定する
U = 20
mu = np.arange(0, 20, 2)

Nsample = 200
OUTDIR = "output"


def run_and_analyze(params):
    U, mu = params
    datfile = run_one(U, mu, Nsample, OUTDIR)
    mean, err = analyze_one(datfile)
    return U, mu, mean, err


def main():
    os.makedirs(OUTDIR, exist_ok=True)

    U_is_sweep = isinstance(U, np.ndarray)
    mu_is_sweep = isinstance(mu, np.ndarray)

    if U_is_sweep and mu_is_sweep:
        raise ValueError("U と mu のどちらか一方を固定値にしてください")
    if not U_is_sweep and not mu_is_sweep:
        raise ValueError("U と mu のどちらか一方を配列にしてください")

    if U_is_sweep:
        sweep_values = U
        fixed_name, fixed_value = "mu", mu
        sweep_name = "U"
        param_grid = [(u, mu) for u in sweep_values]
    else:
        sweep_values = mu
        fixed_name, fixed_value = "U", U
        sweep_name = "mu"
        param_grid = [(U, m) for m in sweep_values]

    max_workers = min(len(param_grid), os.cpu_count() or 1)
    print(f"Sweep {sweep_name} ({len(sweep_values)} points), "
          f"fixed {fixed_name}={fixed_value}, "
          f"{max_workers} workers")

    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_and_analyze, p): p for p in param_grid}
        for future in as_completed(futures):
            p = futures[future]
            try:
                U_val, mu_val, mean, err = future.result()
                results[(U_val, mu_val)] = (mean, err)
                print(f"U={U_val}, mu={mu_val} completed")
            except Exception as e:
                print(f"U={p[0]}, mu={p[1]} failed: {e}")

    # 結果を集約してプロット
    corr_mean_list = []
    corr_err_list = []
    for v in sweep_values:
        key = (v, fixed_value) if U_is_sweep else (fixed_value, v)
        mean, err = results.get(key, (np.nan, 0.0))
        corr_mean_list.append(mean)
        corr_err_list.append(err)

    figname = plot_sweep(
        sweep_values, corr_mean_list, corr_err_list,
        sweep_name, fixed_name, fixed_value, Nsample, OUTDIR,
    )
    print(f"Saved {figname}")


if __name__ == "__main__":
    main()
