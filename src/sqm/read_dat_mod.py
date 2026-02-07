"""Fortran バイナリデータの読み込み・ジャックナイフ解析・相関関数プロットモジュール"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import seaborn

logger = logging.getLogger(__name__)


def configure_plot() -> None:
    """matplotlib / seaborn のグローバル設定を行う。

    モジュール読み込み時の副作用を避けるため、明示的に呼び出す。
    """
    seaborn.set_theme(style="darkgrid", font_scale=1.5)
    matplotlib.use("Agg")


# モジュール読み込み時にプロット設定を適用（後方互換性のため）
configure_plot()


def read_dat(filename: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Fortranバイナリファイルからヘッダーとボディを読み込む。

    Parameters
    ----------
    filename : str | Path
        読み込むバイナリファイルのパス

    Returns
    -------
    Tuple[np.ndarray, np.ndarray]
        (header, body) のタプル

    Raises
    ------
    FileNotFoundError
        ファイルが存在しない場合
    ValueError
        ファイルが空の場合、またはヘッダーの Nx が不正な場合
    """
    filepath = Path(filename)

    if not filepath.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {filepath}")

    if filepath.stat().st_size == 0:
        raise ValueError(f"ファイルが空です: {filepath}")

    head, tail = ("head", "<i"), ("tail", "<i")
    header_dtype = np.dtype([head, ("Nx", "<i"), ("U", "<f8"), ("mu", "<f8"), ("Ntau", "<i"), tail])

    with open(filepath, "rb") as fd:
        header = np.fromfile(fd, dtype=header_dtype, count=1)

        if len(header) == 0:
            raise ValueError(f"ヘッダーが空です: {filepath}")

        Nx = int(header[0]["Nx"])

        if not 1 <= Nx <= 1000:
            raise ValueError(f"Nx の値が不正です (1-1000 の範囲外): {Nx}")

        body_dtype = np.dtype([head, ("a", f"<{Nx}c16"), ("a_ast", f"<{Nx}c16"), tail])
        body = np.fromfile(fd, dtype=body_dtype, count=-1)

    logger.debug("ヘッダー読み込み完了: Nx=%d", Nx)
    return header, body


def jackknife(arr: npt.ArrayLike) -> tuple[float, float]:
    """ジャックナイフ法による平均と誤差の推定 (O(n))。

    Parameters
    ----------
    arr : npt.ArrayLike
        サンプル配列（複素数の場合は実部のみ使用）

    Returns
    -------
    Tuple[float, float]
        (平均値, 誤差) のタプル
    """
    arr = np.real(np.asarray(arr))
    n: int = len(arr)
    total: float = float(np.sum(arr))
    jk_mean: npt.NDArray[np.float64] = (total - arr) / (n - 1)
    jk_mm: float = total / n
    var: float = float(np.sum((jk_mean - jk_mm) ** 2)) / n
    err: float = float(np.sqrt((n - 1) * var))
    return jk_mm, err


def compute_correlation(
    a_list: list,
    a_ast_list: list,
    Nx: int,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """空間相関関数 <a[0] * a*[x]> を計算する。

    Parameters
    ----------
    a_list : list
        各サンプルの a 配列のリスト
    a_ast_list : list
        各サンプルの a* 配列のリスト
    Nx : int
        格子サイズ

    Returns
    -------
    Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        (相関関数平均, 相関関数誤差) のタプル
    """
    N: int = len(a_list)
    corr_mean: npt.NDArray[np.float64] = np.zeros(Nx, dtype=np.float64)
    corr_err: npt.NDArray[np.float64] = np.zeros(Nx, dtype=np.float64)

    for x in range(Nx):
        corr_arr = [np.real(a_list[i][0] * a_ast_list[i][x]) for i in range(N)]
        corr_mean[x], corr_err[x] = jackknife(corr_arr)

    return corr_mean, corr_err


def plot_correlation(
    xarr: npt.NDArray,
    corr_mean: npt.NDArray,
    corr_err: npt.NDArray,
    mu: float,
    U: float,
    Ntau: int,
    N: int,
    savepath: str | Path,
) -> None:
    """相関関数をプロットして保存する。

    Parameters
    ----------
    xarr : npt.NDArray
        x 座標配列
    corr_mean : npt.NDArray
        相関関数平均
    corr_err : npt.NDArray
        相関関数誤差
    mu : float
        化学ポテンシャル
    U : float
        相互作用パラメータ
    Ntau : int
        虚時間刻み数
    N : int
        サンプル数
    savepath : str | Path
        保存先パス
    """
    savepath = Path(savepath)
    savepath.parent.mkdir(parents=True, exist_ok=True)

    plt.close()
    plt.figure(dpi=100)
    plt.title(f"$\\mu$={mu:.1f}, U={U:.1f}")
    plt.ylabel(r"<$a_0 a_i^*$>")
    plt.xlabel("$i$")
    plt.errorbar(xarr, corr_mean, yerr=corr_err)
    plt.savefig(savepath, bbox_inches="tight", pad_inches=0.0)
    logger.info("プロット保存完了: %s", savepath)


def readfile(filename: str | Path) -> float:
    """データ読み込み・相関計算・プロット保存を行い、格子中央の相関値を返す。

    Parameters
    ----------
    filename : str | Path
        Fortran バイナリファイルのパス

    Returns
    -------
    float
        格子中央位置での相関関数値

    Raises
    ------
    FileNotFoundError
        ファイルが存在しない場合
    ValueError
        ファイルの内容が不正な場合
    """
    filepath = Path(filename)
    header, body = read_dat(filepath)

    a_list = [b["a"] for b in body]
    a_ast_list = [b["a_ast"] for b in body]
    N: int = len(body)

    Ntau: int = int(header[0]["Ntau"])
    U: float = float(header[0]["U"])
    mu: float = float(header[0]["mu"])
    Nx: int = int(header[0]["Nx"])

    corr_mean, corr_err = compute_correlation(a_list, a_ast_list, Nx)

    logger.info("num. of samples: %d", N)

    xarr: npt.NDArray[np.float64] = np.arange(Nx, dtype=np.float64)
    savepath = (
        filepath.parent.parent / "figures" / f"mu={mu:.1f},U={U:.1f},tau={Ntau:.0f},N={N}.png"
    )
    plot_correlation(xarr, corr_mean, corr_err, mu, U, Ntau, N, savepath)

    return float(corr_mean[Nx // 2])
