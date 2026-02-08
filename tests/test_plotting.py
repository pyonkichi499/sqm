"""plotting.py のテスト

相関関数プロットおよびスイープサマリープロットのテスト。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from sqm.plotting import plot_correlation, plot_sweep_summary

# ============================================================
# 1. plot_correlation() のテスト
# ============================================================


class TestPlotCorrelation:
    """plot_correlation() のテスト群"""

    def test_plot_correlation_ファイルを正しく保存する(self, tmp_path: Path) -> None:
        xarr = np.array([0.0, 1.0, 2.0])
        corr_mean = np.array([1.0, 0.5, 0.2])
        corr_err = np.array([0.1, 0.05, 0.02])
        savepath = tmp_path / "test_plot.png"

        plot_correlation(
            xarr, corr_mean, corr_err, mu=0.5, U=1.0, Ntau=10, N=100, savepath=savepath
        )

        assert savepath.exists()
        assert savepath.stat().st_size > 0

    def test_plot_correlation_ディレクトリを自動作成する(self, tmp_path: Path) -> None:
        xarr = np.array([0.0, 1.0])
        corr_mean = np.array([1.0, 0.5])
        corr_err = np.array([0.1, 0.05])
        # 存在しないネストされたディレクトリ
        savepath = tmp_path / "deep" / "nested" / "dir" / "plot.png"

        plot_correlation(
            xarr, corr_mean, corr_err, mu=0.5, U=1.0, Ntau=10, N=100, savepath=savepath
        )

        assert savepath.exists()
        assert savepath.stat().st_size > 0


# ============================================================
# 2. plot_sweep_summary() のテスト
# ============================================================


class TestPlotSweepSummary:
    """plot_sweep_summary() のテスト群"""

    def test_plot_sweep_summary_ファイルを正しく保存する(self, tmp_path: Path) -> None:
        sweep_values = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        corr_values = [0.8, 0.6, 0.4, 0.3, 0.2]
        savepath = tmp_path / "sweep_summary.png"

        plot_sweep_summary(
            sweep_values=sweep_values,
            corr_values=corr_values,
            sweep_name="mu",
            fixed_name="U",
            fixed_value=1.0,
            n_samples=1000,
            savepath=savepath,
        )

        assert savepath.exists()
        assert savepath.stat().st_size > 0

    def test_plot_sweep_summary_ディレクトリを自動作成する(self, tmp_path: Path) -> None:
        sweep_values = np.array([0.5, 1.0, 1.5])
        corr_values = [0.5, 0.3, 0.1]
        savepath = tmp_path / "deep" / "nested" / "dir" / "sweep.png"

        plot_sweep_summary(
            sweep_values=sweep_values,
            corr_values=corr_values,
            sweep_name="U",
            fixed_name="mu",
            fixed_value=0.5,
            n_samples=500,
            savepath=savepath,
        )

        assert savepath.exists()
        assert savepath.stat().st_size > 0

    def test_plot_sweep_summary_muスイープで正しいラベル(self, tmp_path: Path) -> None:
        sweep_values = np.array([0.0, 1.0, 2.0])
        corr_values = [0.9, 0.5, 0.1]
        savepath = tmp_path / "mu_sweep.png"

        with patch("matplotlib.pyplot") as mock_plt:
            plot_sweep_summary(
                sweep_values=sweep_values,
                corr_values=corr_values,
                sweep_name="mu",
                fixed_name="U",
                fixed_value=2.0,
                n_samples=100,
                savepath=savepath,
            )

            mock_plt.xlabel.assert_called_once_with(r"$\mu$")
            mock_plt.ylabel.assert_called_once_with(r"$\langle a_0 a_{N/2}^* \rangle$")
            mock_plt.title.assert_called_once_with("U=2.0, N=100")
