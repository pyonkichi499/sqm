import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn
seaborn.set_theme(style="darkgrid", font_scale=1.5)
matplotlib.use("Agg")


def read_dat(filename):
    """Fortranバイナリファイルからヘッダーとボディを読み込む"""
    head, tail = ('head', '<i'), ('tail', '<i')
    header_dtype = np.dtype([
        head,
        ('Nx', '<i'),
        ('U', '<f8'),
        ('mu', '<f8'),
        ('Ntau', '<i'),
        tail])
    with open(filename, 'rb') as fd:
        header = np.fromfile(fd, dtype=header_dtype, count=1)
        Nx = header[0]['Nx']
        body_dtype = np.dtype([
            head,
            ('a', '<{}c16'.format(Nx)),
            ('a_ast', '<{}c16'.format(Nx)),
            tail])
        body = np.fromfile(fd, dtype=body_dtype, count=-1)
    return header, body


def jackknife(arr):
    """ジャックナイフ法による平均と誤差の推定 (O(n))"""
    arr = np.real(np.asarray(arr))
    n = len(arr)
    total = np.sum(arr)
    jk_mean = (total - arr) / (n - 1)
    jk_mm = total / n
    var = np.sum((jk_mean - jk_mm) ** 2) / n
    err = np.sqrt((n - 1) * var)
    return jk_mm, err


def compute_correlation(a_list, a_ast_list, Nx):
    """空間相関関数 <a[0] * a*[x]> を計算する"""
    N = len(a_list)
    corr_mean = np.zeros(Nx, dtype=np.float64)
    corr_err = np.zeros(Nx, dtype=np.float64)

    for x in range(Nx):
        corr_arr = [np.real(a_list[i][0] * a_ast_list[i][x]) for i in range(N)]
        corr_mean[x], corr_err[x] = jackknife(corr_arr)

    return corr_mean, corr_err


def plot_correlation(xarr, corr_mean, corr_err, mu, U, Ntau, N, savepath):
    """相関関数をプロットして保存する"""
    plt.close()
    plt.figure(dpi=100)
    plt.title(f"$\\mu$={mu:.1f}, U={U:.1f}")
    plt.ylabel(r"<$a_0 a_i^*$>")
    plt.xlabel("$i$")
    plt.errorbar(xarr, corr_mean, yerr=corr_err)
    plt.savefig(savepath, bbox_inches="tight", pad_inches=0.0)


def readfile(filename, outdir="output"):
    """データ読み込み・相関計算・プロット保存を行い、格子中央の相関値を返す"""
    header, body = read_dat(filename)

    a_list = [b['a'] for b in body]
    a_ast_list = [b['a_ast'] for b in body]
    N = len(body)

    Ntau = header[0]["Ntau"]
    U = header[0]["U"]
    mu = header[0]["mu"]
    Nx = header[0]['Nx']

    corr_mean, corr_err = compute_correlation(a_list, a_ast_list, Nx)

    print("num. of samples: {}".format(N))

    xarr = np.arange(Nx, dtype=np.float64)
    savepath = os.path.join(outdir, f"mu={mu:.1f},U={U:.1f},tau={Ntau:.0f},N={N}.png")
    plot_correlation(xarr, corr_mean, corr_err, mu, U, Ntau, N, savepath)

    return corr_mean[Nx // 2]
