"""sweep.py のテスト"""
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

import sweep

runner = CliRunner()


class TestSweepValidation:
    def test_error_both_params(self):
        """U と mu の両方を指定するとエラー"""
        result = runner.invoke(sweep.main, ["--U", "20", "--mu", "5"])
        assert result.exit_code != 0
        assert "両方" in result.output or "Error" in result.output

    def test_error_no_params(self):
        """U も mu も指定しないとエラー"""
        result = runner.invoke(sweep.main, [])
        assert result.exit_code != 0
        assert "一方" in result.output or "Error" in result.output


class TestRunAndAnalyze:
    def test_returns_results(self):
        """run_and_analyze が (U, mu, mean, err) を返す"""
        with patch("sweep.run_one") as mock_run, \
             patch("sweep.analyze_one") as mock_analyze:
            mock_run.return_value = "output/test.dat"
            mock_analyze.return_value = (1.5, 0.1)
            result = sweep.run_and_analyze((20, 5, 200, "output"))
        assert result == (20, 5, 1.5, 0.1)

    def test_passes_nsample_and_outdir(self):
        """nsample と outdir が run_one に渡される"""
        with patch("sweep.run_one") as mock_run, \
             patch("sweep.analyze_one") as mock_analyze:
            mock_run.return_value = "output/test.dat"
            mock_analyze.return_value = (0.0, 0.0)
            sweep.run_and_analyze((10, 3, 500, "/tmp/out"))
        assert mock_run.call_args[0][2] == 500
        assert mock_run.call_args[0][3] == "/tmp/out"


class TestSweepCli:
    def test_mu_sweep_with_fixed_u(self):
        """--U 指定でmuスイープ"""
        with patch("sweep.run_and_analyze") as mock_ra, \
             patch("sweep.plot_sweep") as mock_plot:
            mock_ra.return_value = (20, 0, 1.0, 0.1)
            mock_plot.return_value = "output/test.png"
            result = runner.invoke(sweep.main,
                                   ["--U", "20", "--start", "0", "--end", "4", "--step", "2"])
        assert result.exit_code == 0
        assert "Sweep mu" in result.output

    def test_u_sweep_with_fixed_mu(self):
        """--mu 指定でUスイープ"""
        with patch("sweep.run_and_analyze") as mock_ra, \
             patch("sweep.plot_sweep") as mock_plot:
            mock_ra.return_value = (5, 10, 2.0, 0.2)
            mock_plot.return_value = "output/test.png"
            result = runner.invoke(sweep.main,
                                   ["--mu", "10", "--start", "5", "--end", "15", "--step", "5"])
        assert result.exit_code == 0
        assert "Sweep U" in result.output
