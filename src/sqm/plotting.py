"""プロットモジュール

相関関数やスイープ結果の可視化を担当する。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)

__all__ = [
    "configure_plot",
    "plot_correlation",
    "plot_sweep_summary",
    "plot_timeseries",
    "plot_autocorrelation",
    "plot_thermalization_diagnostic",
]

_configured = False


def configure_plot() -> None:
    """matplotlib / seaborn のグローバル設定を行う（初回のみ実行）。"""
    global _configured  # noqa: PLW0603
    if _configured:
        return
    import matplotlib
    import seaborn

    matplotlib.use("Agg")
    seaborn.set_theme(style="darkgrid", font_scale=1.5)
    _configured = True


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
    import matplotlib.pyplot as plt

    configure_plot()
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


def plot_sweep_summary(
    sweep_values: npt.NDArray,
    corr_values: list[float],
    sweep_name: str,
    fixed_name: str,
    fixed_value: float,
    n_samples: int,
    savepath: str | Path,
) -> None:
    """パラメータスイープのサマリープロットを保存する。

    Parameters
    ----------
    sweep_values : npt.NDArray
        スイープしたパラメータの値配列
    corr_values : list[float]
        各スイープ点での格子中央相関値
    sweep_name : str
        スイープパラメータ名 ("mu" or "U")
    fixed_name : str
        固定パラメータ名 ("U" or "mu")
    fixed_value : float
        固定パラメータの値
    n_samples : int
        サンプル数
    savepath : str | Path
        保存先パス
    """
    import matplotlib.pyplot as plt

    configure_plot()
    savepath = Path(savepath)
    savepath.parent.mkdir(parents=True, exist_ok=True)

    plt.close()
    plt.figure(dpi=100)
    plt.plot(sweep_values, corr_values, "o-")
    xlabel = r"$\mu$" if sweep_name == "mu" else f"${sweep_name}$"
    plt.xlabel(xlabel)
    plt.ylabel(r"$\langle a_0 a_{N/2}^* \rangle$")
    plt.title(f"{fixed_name}={fixed_value}, N={n_samples}")
    plt.savefig(savepath, bbox_inches="tight")
    logger.info("スイープサマリープロット保存完了: %s", savepath)


def plot_timeseries(
    data: npt.NDArray,
    savepath: str | Path,
    *,
    thermalization_skip: int = 0,
    ylabel: str = "Observable",
    title: str = "",
) -> None:
    """時系列データをプロットし、thermalization 境界を表示する。

    Parameters
    ----------
    data : npt.NDArray
        1次元の時系列データ
    savepath : str | Path
        保存先パス
    thermalization_skip : int
        thermalization でスキップするサンプル数（境界線を描画）
    ylabel : str
        y軸ラベル
    title : str
        プロットタイトル
    """
    import matplotlib.pyplot as plt

    configure_plot()
    savepath = Path(savepath)
    savepath.parent.mkdir(parents=True, exist_ok=True)

    plt.close()
    plt.figure(dpi=100)
    plt.plot(data, linewidth=0.5)
    if thermalization_skip > 0:
        plt.axvline(x=thermalization_skip, color="red", linestyle="--", label="thermalization")
        plt.legend()
    plt.xlabel("Sample")
    plt.ylabel(ylabel)
    if title:
        plt.title(title)
    plt.savefig(savepath, bbox_inches="tight")
    logger.info("時系列プロット保存完了: %s", savepath)


def plot_autocorrelation(
    acf: npt.NDArray,
    savepath: str | Path,
    *,
    tau_int: float | None = None,
    title: str = "",
) -> None:
    """自己相関関数をプロットする。

    Parameters
    ----------
    acf : npt.NDArray
        自己相関関数（ラグ0=1）
    savepath : str | Path
        保存先パス
    tau_int : float | None
        積分自己相関時間（表示用）
    title : str
        プロットタイトル
    """
    import matplotlib.pyplot as plt

    configure_plot()
    savepath = Path(savepath)
    savepath.parent.mkdir(parents=True, exist_ok=True)

    plt.close()
    plt.figure(dpi=100)
    lags = list(range(len(acf)))
    plt.plot(lags, acf)
    plt.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    if tau_int is not None:
        plt.axvline(x=tau_int, color="red", linestyle="--", label=f"$\\tau_{{int}}$={tau_int:.1f}")
        plt.legend()
    plt.xlabel("Lag")
    plt.ylabel(r"$\rho(k)$")
    if title:
        plt.title(title)
    plt.savefig(savepath, bbox_inches="tight")
    logger.info("自己相関プロット保存完了: %s", savepath)


def plot_thermalization_diagnostic(
    data: npt.NDArray,
    savepath: str | Path,
    *,
    window_size: int = 10,
    thermalization_skip: int = 0,
    title: str = "",
) -> None:
    """thermalization 診断プロット：移動平均 + 定常状態境界を表示する。

    Parameters
    ----------
    data : npt.NDArray
        1次元の時系列データ
    savepath : str | Path
        保存先パス
    window_size : int
        移動平均のウィンドウサイズ
    thermalization_skip : int
        検出されたスキップ数
    title : str
        プロットタイトル
    """
    import matplotlib.pyplot as plt
    import numpy as np_local

    configure_plot()
    savepath = Path(savepath)
    savepath.parent.mkdir(parents=True, exist_ok=True)

    n = len(data)
    n_windows = n // window_size
    window_means = np_local.array(
        [np_local.mean(data[i * window_size : (i + 1) * window_size]) for i in range(n_windows)]
    )
    window_centers = np_local.array(
        [(i + 0.5) * window_size for i in range(n_windows)]
    )

    # 後半の統計
    stationary_start = n_windows // 2
    stationary_mean = float(np_local.mean(window_means[stationary_start:]))
    stationary_std = float(np_local.std(window_means[stationary_start:]))

    plt.close()
    plt.figure(dpi=100)
    plt.plot(data, alpha=0.3, linewidth=0.5, label="raw data")
    plt.plot(window_centers, window_means, "o-", markersize=3, label="window mean")
    plt.axhline(y=stationary_mean, color="green", linestyle="-", label="stationary mean")
    if stationary_std > 0:
        plt.axhspan(
            stationary_mean - 3 * stationary_std,
            stationary_mean + 3 * stationary_std,
            alpha=0.2, color="green",
        )
    if thermalization_skip > 0:
        plt.axvline(x=thermalization_skip, color="red", linestyle="--", label="thermalization")
    plt.xlabel("Sample")
    plt.ylabel("Observable")
    plt.legend(fontsize=8)
    if title:
        plt.title(title)
    plt.savefig(savepath, bbox_inches="tight")
    logger.info("thermalization 診断プロット保存完了: %s", savepath)
