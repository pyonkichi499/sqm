import os
import numpy as np
import matplotlib.pyplot as plt
from subprocess import run
from concurrent.futures import ProcessPoolExecutor, as_completed

import read_dat_mod
import wparams

U_0 = 5
U_end = 40
s = "1d0"  # used only filename
Nsample = 200
U_list = np.arange(U_0, U_end, 10)


def run_simulation(U):
    """1つのU値に対するシミュレーション実行と解析を行う"""
    mu = 0.4 * U

    datfilename = f"U={U},s={s}.dat"
    paramsfile = f"params_U={U}.dat"

    # 固有のパラメータファイルを書き出し
    wparams.write_params(mu, U, Nsample, datfilename, paramsfile=paramsfile)

    # Fortranシミュレーション実行
    run(["./a.out", paramsfile])

    # 一時パラメータファイルを削除
    os.remove(paramsfile)

    # 解析
    corr_val = read_dat_mod.readfile(datfilename)
    return U, corr_val


if __name__ == "__main__":
    # 利用可能なCPU数（最大でU_listの長さまで）
    max_workers = min(len(U_list), os.cpu_count() or 1)
    print(f"Running {len(U_list)} simulations with {max_workers} workers")

    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_simulation, U): U for U in U_list}
        for future in as_completed(futures):
            U = futures[future]
            try:
                U_val, corr_val = future.result()
                results[U_val] = corr_val
                print(f"U={U_val} completed")
            except Exception as e:
                print(f"U={U} failed: {e}")

    # U順にソートして結果をまとめる
    sorted_Us = sorted(results.keys())
    corr_a_list = [results[U] for U in sorted_Us]

    plt.close()
    plt.errorbar(sorted_Us, corr_a_list)
    plt.savefig(f"U={U_0}~{U_end},N={Nsample}.png")
