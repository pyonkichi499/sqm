import os
import numpy as np
import matplotlib.pyplot as plt
from subprocess import run
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product

import read_dat_mod
import wparams

# パラメータグリッド
U_list = np.arange(5, 40, 10)
mu_list = np.arange(0, 20, 2)
Nsample = 200
s = "1d0"  # ファイル名用


def run_simulation(params):
    """1つの(U, mu)に対するシミュレーション実行と解析を行う"""
    U, mu = params

    datfilename = f"U={U},mu={mu},s={s}.dat"
    paramsfile = f"params_U={U}_mu={mu}.dat"

    wparams.write_params(mu, U, Nsample, datfilename, paramsfile=paramsfile)
    run(["./a.out", paramsfile])
    os.remove(paramsfile)

    corr_val = read_dat_mod.readfile(datfilename)
    return U, mu, corr_val


if __name__ == "__main__":
    param_grid = list(product(U_list, mu_list))
    max_workers = min(len(param_grid), os.cpu_count() or 1)
    print(f"Running {len(param_grid)} simulations with {max_workers} workers")

    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_simulation, p): p for p in param_grid}
        for future in as_completed(futures):
            p = futures[future]
            try:
                U, mu, corr_val = future.result()
                results[(U, mu)] = corr_val
                print(f"U={U}, mu={mu} completed")
            except Exception as e:
                print(f"U={p[0]}, mu={p[1]} failed: {e}")

    # 結果を2Dグリッドに整形
    corr_grid = np.full((len(U_list), len(mu_list)), np.nan)
    for i, U in enumerate(U_list):
        for j, mu in enumerate(mu_list):
            if (U, mu) in results:
                corr_grid[i, j] = results[(U, mu)]

    # ヒートマップで位相図を描く
    plt.close()
    plt.figure(dpi=100)
    plt.pcolormesh(mu_list, U_list, corr_grid, shading="nearest")
    plt.colorbar(label=r"$\langle a_0 a_{N/2}^* \rangle$")
    plt.xlabel(r"$\mu$")
    plt.ylabel(r"$U$")
    plt.title(f"N={Nsample}")
    plt.savefig(f"phase_diagram_N={Nsample}.png", bbox_inches="tight")
    print(f"Saved phase_diagram_N={Nsample}.png")
