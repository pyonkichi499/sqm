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
