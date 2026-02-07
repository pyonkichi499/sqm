import os
import numpy as np
import matplotlib.pyplot as plt
from subprocess import run
from concurrent.futures import ProcessPoolExecutor, as_completed

import read_dat_mod
import wparams

# === 設定 ===
# 片方を固定値(スカラー)、もう片方をスイープ範囲(配列)で指定する
U = 20
mu = np.arange(0, 20, 2)

Nsample = 200
s = "1d0"
OUTDIR = "output"


def run_simulation(params):
    """1つの(U, mu)に対するシミュレーション実行と解析を行う"""
    U, mu = params

    datfilename = os.path.join(OUTDIR, f"U={U},mu={mu},s={s}.dat")
    paramsfile = os.path.join(OUTDIR, f"params_U={U}_mu={mu}.dat")

    wparams.write_params(mu, U, Nsample, datfilename, paramsfile=paramsfile)
    run(["./a.out", paramsfile])
    os.remove(paramsfile)

    header, body = read_dat_mod.read_dat(datfilename)
    Nx = header[0]['Nx']
    a_list = [b['a'] for b in body]
    a_ast_list = [b['a_ast'] for b in body]
    corr_mean, corr_err = read_dat_mod.compute_correlation(a_list, a_ast_list, Nx)
    mid = Nx // 2
    return U, mu, corr_mean[mid], corr_err[mid]


if __name__ == "__main__":
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
        futures = {executor.submit(run_simulation, p): p for p in param_grid}
        for future in as_completed(futures):
            p = futures[future]
            try:
                U_val, mu_val, mean, err = future.result()
                results[(U_val, mu_val)] = (mean, err)
                print(f"U={U_val}, mu={mu_val} completed")
            except Exception as e:
                print(f"U={p[0]}, mu={p[1]} failed: {e}")

    # スイープ順に結果を並べる
    corr_mean_list = []
    corr_err_list = []
    for v in sweep_values:
        key = (v, fixed_value) if U_is_sweep else (fixed_value, v)
        mean, err = results.get(key, (np.nan, 0.0))
        corr_mean_list.append(mean)
        corr_err_list.append(err)

    # プロット
    plt.close()
    plt.figure(dpi=100)
    plt.errorbar(sweep_values, corr_mean_list, yerr=corr_err_list, fmt="o-")
    xlabel = r"$\mu$" if sweep_name == "mu" else f"${sweep_name}$"
    plt.xlabel(xlabel)
    plt.ylabel(r"$\langle a_0 a_{N/2}^* \rangle$")
    plt.title(f"{fixed_name}={fixed_value}, N={Nsample}")

    figname = os.path.join(OUTDIR, f"sweep_{sweep_name}_{fixed_name}={fixed_value}_N={Nsample}.png")
    plt.savefig(figname, bbox_inches="tight")
    print(f"Saved {figname}")
