"""output/*.dat から結果を集約してプロット"""
import os
import re
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn
seaborn.set_theme(style="darkgrid", font_scale=1.5)

import read_dat_mod


def analyze_one(datfilename):
    """1つの.datファイルから格子中央の相関値(mean, err)を返す"""
    header, body = read_dat_mod.read_dat(datfilename)
    Nx = header[0]['Nx']
    a_list = [b['a'] for b in body]
    a_ast_list = [b['a_ast'] for b in body]
    corr_mean, corr_err = read_dat_mod.compute_correlation(a_list, a_ast_list, Nx)
    mid = Nx // 2
    return corr_mean[mid], corr_err[mid]


def collect_results(outdir):
    """outdir 内の .dat ファイルからパラメータと相関値を収集"""
    pattern = re.compile(r"U=([\d.]+),mu=([\d.]+)\.dat$")
    results = {}
    for fname in os.listdir(outdir):
        m = pattern.match(fname)
        if not m:
            continue
        U = float(m.group(1))
        mu = float(m.group(2))
        try:
            mean, err = analyze_one(os.path.join(outdir, fname))
            results[(U, mu)] = (mean, err)
        except Exception as e:
            print(f"Skip {fname}: {e}")
    return results


def plot_sweep(sweep_values, corr_mean_list, corr_err_list,
               sweep_name, fixed_name, fixed_value, Nsample, outdir):
    """スイープ結果をerrorbar付き折れ線グラフで保存"""
    plt.close()
    plt.figure(dpi=100)
    plt.errorbar(sweep_values, corr_mean_list, yerr=corr_err_list, fmt="o-")
    xlabel = r"$\mu$" if sweep_name == "mu" else f"${sweep_name}$"
    plt.xlabel(xlabel)
    plt.ylabel(r"$\langle a_0 a_{N/2}^* \rangle$")
    plt.title(f"{fixed_name}={fixed_value}, N={Nsample}")

    figname = os.path.join(outdir, f"sweep_{sweep_name}_{fixed_name}={fixed_value}_N={Nsample}.png")
    plt.savefig(figname, bbox_inches="tight")
    return figname


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "output"

    results = collect_results(outdir)
    if not results:
        print(f"No .dat files found in {outdir}/")
        sys.exit(1)

    # パラメータ構造を自動判定: U or mu のどちらが変動しているか
    U_values = sorted(set(k[0] for k in results))
    mu_values = sorted(set(k[1] for k in results))

    if len(U_values) == 1:
        sweep_name, sweep_values = "mu", mu_values
        fixed_name, fixed_value = "U", U_values[0]
    elif len(mu_values) == 1:
        sweep_name, sweep_values = "U", U_values
        fixed_name, fixed_value = "mu", mu_values[0]
    else:
        print(f"Mixed parameters: {len(U_values)} U values, {len(mu_values)} mu values")
        print("Cannot auto-detect sweep axis. Use sweep.py for structured sweeps.")
        sys.exit(1)

    corr_mean_list = []
    corr_err_list = []
    for v in sweep_values:
        key = (v, fixed_value) if sweep_name == "U" else (fixed_value, v)
        mean, err = results.get(key, (np.nan, 0.0))
        corr_mean_list.append(mean)
        corr_err_list.append(err)

    Nsample = "?"  # .dat からは取れないのでプレースホルダ
    figname = plot_sweep(
        sweep_values, corr_mean_list, corr_err_list,
        sweep_name, fixed_name, fixed_value, Nsample, outdir,
    )
    print(f"Saved {figname}")


if __name__ == "__main__":
    main()
