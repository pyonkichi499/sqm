"""runner.py のテスト

実行エンジン (runner.py) のデータ構造および実行関数のテスト。
Fortran シミュレーションの実行は mock で置き換える。
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from concurrent.futures import Future
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sqm.config import Config, PathConfig, SimulationConfig, SweepConfig
from sqm.runner import (
    PointResult,
    SweepResult,
    _build_param_grid,
    _prepare_run_directory,
    _reset_signals,
    _run_fortran_with_progress,
    run_single_point,
    run_sweep,
)

# ============================================================
# テスト用ヘルパー
# ============================================================


class _SequentialExecutor:
    """ProcessPoolExecutor の代替として逐次実行するヘルパークラス。

    ProcessPoolExecutor は関数を pickle して子プロセスに送るため、
    MagicMock をそのまま渡せない。テスト時にはこのクラスで置き換える。
    """

    def __init__(self, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> _SequentialExecutor:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def shutdown(self, *, wait: bool = True, cancel_futures: bool = False) -> None:
        pass

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:
        future: Future[Any] = Future()
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        return future


def _create_test_binary(
    filepath: Path,
    Nx: int = 4,
    n_samples: int = 2,
    U: float = 1.0,
    mu: float = 0.5,
    Ntau: int = 10,
) -> None:
    """テスト用の Fortran バイナリファイルを作成するヘルパー。

    Fortran の unformatted sequential write は
    [record_length (4 bytes)] [data] [record_length (4 bytes)]
    という形式で各レコードを書く。
    """
    # ヘッダーレコード: Nx(i4), U(f8), mu(f8), Ntau(i4) = 4+8+8+4 = 24 bytes
    header_data = struct.pack("<i d d i", Nx, U, mu, Ntau)
    record_len = len(header_data)  # 24
    header_record = struct.pack("<i", record_len) + header_data + struct.pack("<i", record_len)

    body_records = b""
    for i in range(n_samples):
        # a: Nx 個の complex128 (各 16 bytes)
        # a_ast: Nx 個の complex128 (各 16 bytes)
        a_values = [complex(float(j + 1 + i * 0.1), 0.0) for j in range(Nx)]
        a_ast_values = [complex(float(j + 1 + i * 0.1), 0.0) for j in range(Nx)]

        body_data = b""
        for v in a_values:
            body_data += struct.pack("<d d", v.real, v.imag)
        for v in a_ast_values:
            body_data += struct.pack("<d d", v.real, v.imag)

        body_record_len = len(body_data)  # Nx * 16 * 2
        body_records += (
            struct.pack("<i", body_record_len) + body_data + struct.pack("<i", body_record_len)
        )

    filepath.write_bytes(header_record + body_records)


# ============================================================
# 1. PointResult のテスト
# ============================================================


class TestPointResult:
    """PointResult データクラスのテスト群"""

    def test_PointResult_フィールドを正しく保持する(self) -> None:
        """全フィールドを指定して PointResult を生成し、各値を検証する"""
        corr_mean = np.array([1.0, 0.5, 0.2, 0.1])
        corr_err = np.array([0.1, 0.05, 0.02, 0.01])
        dat_path = Path("/tmp/test.dat")

        result = PointResult(
            U=20.0,
            mu=3.0,
            correlation_midpoint=0.2,
            correlation_mean=corr_mean,
            correlation_err=corr_err,
            corrected_mean=0.19,
            corrected_error_val=0.03,
            n_eff=50.0,
            thermalization_skip=10,
            n_samples=200,
            dat_filepath=dat_path,
        )

        assert pytest.approx(20.0) == result.U
        assert result.mu == pytest.approx(3.0)
        assert result.correlation_midpoint == pytest.approx(0.2)
        np.testing.assert_array_equal(result.correlation_mean, corr_mean)
        np.testing.assert_array_equal(result.correlation_err, corr_err)
        assert result.corrected_mean == pytest.approx(0.19)
        assert result.corrected_error_val == pytest.approx(0.03)
        assert result.n_eff == pytest.approx(50.0)
        assert result.thermalization_skip == 10
        assert result.n_samples == 200
        assert result.dat_filepath == dat_path

    def test_PointResult_デフォルト値が設定される(self) -> None:
        """最小限の必須引数のみで生成し、デフォルト値を検証する"""
        result = PointResult(
            U=10.0,
            mu=1.0,
            correlation_midpoint=0.5,
            correlation_mean=np.zeros(4),
            correlation_err=np.zeros(4),
        )

        assert result.corrected_mean is None
        assert result.corrected_error_val is None
        assert result.n_eff is None
        assert result.thermalization_skip == 0
        assert result.n_samples == 0
        assert result.dat_filepath == Path(".")


# ============================================================
# 2. SweepResult のテスト
# ============================================================


class TestSweepResult:
    """SweepResult データクラスのテスト群"""

    def test_SweepResult_空のリストで生成できる(self) -> None:
        """空の points と failed で SweepResult を生成する"""
        result = SweepResult()

        assert result.points == []
        assert result.failed == []
        assert result.walltime_seconds == 0.0
        assert result.success_rate == 0.0

    def test_SweepResult_成功率が正しく計算される(self) -> None:
        """3 ポイント成功、1 ポイント失敗で成功率 75% を確認する"""
        fake_points = [
            PointResult(
                U=20.0,
                mu=float(i),
                correlation_midpoint=0.5,
                correlation_mean=np.zeros(4),
                correlation_err=np.zeros(4),
                n_samples=100,
            )
            for i in range(3)
        ]
        failed = [(20.0, 3.0, "error message")]

        result = SweepResult(
            points=fake_points,
            failed=failed,
        )

        assert result.success_rate == pytest.approx(0.75)

    def test_SweepResult_全て失敗の場合の成功率(self) -> None:
        """全ポイントが失敗した場合、成功率は 0% になる"""
        failed = [
            (20.0, 0.0, "error 1"),
            (20.0, 1.0, "error 2"),
        ]

        result = SweepResult(failed=failed)

        assert result.success_rate == pytest.approx(0.0)


# ============================================================
# 3. run_single_point() のテスト
# ============================================================


class TestRunSinglePoint:
    """run_single_point() のテスト群"""

    @patch("sqm.runner.subprocess.run")
    def test_run_single_point_正常実行でPointResultを返す(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """subprocess をモックし、偽のバイナリファイルを読み込んで
        PointResult が正しく返されることを確認する"""
        config = Config(
            simulation=SimulationConfig(Nsample=5),
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
        )

        # Fortran シミュレーションが生成するはずの偽バイナリを事前作成
        dat_path = tmp_path / "U=20.0,mu=0.5,s=1d0.dat"
        _create_test_binary(dat_path, Nx=4, n_samples=5, U=20.0, mu=0.5)

        # subprocess.run をモック（何もしない）
        mock_run.return_value = MagicMock(returncode=0)

        result = run_single_point(U=20.0, mu=0.5, config=config, skip_autocorrelation=True)

        assert isinstance(result, PointResult)
        assert pytest.approx(20.0) == result.U
        assert result.mu == pytest.approx(0.5)
        assert result.n_samples == 5
        assert len(result.correlation_mean) == 4
        assert len(result.correlation_err) == 4
        assert result.dat_filepath == dat_path

        # subprocess.run が呼ばれたことを確認
        mock_run.assert_called_once()

    def test_run_single_point_Fortranバイナリが見つからない場合にエラー(
        self, tmp_path: Path
    ) -> None:
        """存在しない Fortran バイナリを指定した場合、エラーが発生する"""
        config = Config(
            simulation=SimulationConfig(Nsample=5),
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/nonexistent/path/a.out"),
            ),
        )

        with pytest.raises((FileNotFoundError, OSError)):
            run_single_point(U=20.0, mu=0.5, config=config)

    @patch("sqm.runner.subprocess.run")
    def test_run_single_point_autocorrelationスキップ時にNoneを返す(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """skip_autocorrelation=True の場合、corrected_mean と n_eff が None"""
        config = Config(
            simulation=SimulationConfig(Nsample=30),
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
        )

        # 30 サンプルの偽バイナリ（n_samples > 20 でも skip するケース）
        dat_path = tmp_path / "U=10.0,mu=1.0,s=1d0.dat"
        _create_test_binary(dat_path, Nx=4, n_samples=30, U=10.0, mu=1.0)

        mock_run.return_value = MagicMock(returncode=0)

        result = run_single_point(U=10.0, mu=1.0, config=config, skip_autocorrelation=True)

        assert result.corrected_mean is None
        assert result.corrected_error_val is None
        assert result.n_eff is None
        assert result.n_samples == 30


# ============================================================
# 4. run_sweep() のテスト
# ============================================================


class TestRunSweep:
    """run_sweep() のテスト群"""

    def test_run_sweep_sweep設定なしでValueError(self, tmp_path: Path) -> None:
        """config.sweep が None の場合、ValueError を送出する"""
        config = Config(
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
            ),
            sweep=None,
        )

        with pytest.raises(ValueError, match="スイープ設定が必要です"):
            run_sweep(config)

    @patch("sqm.runner.plot_sweep_summary")
    @patch("sqm.runner.plot_correlation")
    @patch(
        "sqm.runner.ProcessPoolExecutor",
        new=_SequentialExecutor,
    )
    @patch("sqm.runner.run_single_point")
    def test_run_sweep_全ポイント実行される(
        self,
        mock_rsp: MagicMock,
        mock_plot_corr: MagicMock,
        mock_plot_summary: MagicMock,
        tmp_path: Path,
    ) -> None:
        """run_single_point がスイープ値ごとに呼ばれることを確認する"""
        config = Config(
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
            ),
            sweep=SweepConfig(U=20.0, mu_start=0.0, mu_end=4.0, mu_step=2.0),
        )

        # 各呼び出しに対して異なる mu を持つ PointResult を返す
        def side_effect(U: float, mu: float, cfg: Config, **kwargs: object) -> PointResult:
            return PointResult(
                U=U,
                mu=mu,
                correlation_midpoint=1.0 / (1.0 + mu),
                correlation_mean=np.zeros(4),
                correlation_err=np.zeros(4),
                n_samples=5,
            )

        mock_rsp.side_effect = side_effect

        result = run_sweep(config, max_workers=1)

        # mu=0.0 と mu=2.0 の 2 点が実行される
        assert len(result.points) == 2
        assert mock_rsp.call_count == 2
        assert len(result.failed) == 0
        assert result.success_rate == pytest.approx(1.0)

        # ソートされていることを確認（mu 昇順）
        assert result.points[0].mu <= result.points[1].mu

    @patch("sqm.runner.plot_sweep_summary")
    @patch("sqm.runner.plot_correlation")
    @patch(
        "sqm.runner.ProcessPoolExecutor",
        new=_SequentialExecutor,
    )
    @patch("sqm.runner.run_single_point")
    def test_run_sweep_失敗ポイントがfailedに記録される(
        self,
        mock_rsp: MagicMock,
        mock_plot_corr: MagicMock,
        mock_plot_summary: MagicMock,
        tmp_path: Path,
    ) -> None:
        """一部のポイントが例外を投げた場合、failed リストに記録される"""
        config = Config(
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
            ),
            sweep=SweepConfig(U=20.0, mu_start=0.0, mu_end=6.0, mu_step=2.0),
        )

        # mu=2.0 の場合のみ例外を発生させる
        def side_effect(U: float, mu: float, cfg: Config, **kwargs: object) -> PointResult:
            if mu == pytest.approx(2.0):
                raise RuntimeError("Fortran シミュレーション失敗")
            return PointResult(
                U=U,
                mu=mu,
                correlation_midpoint=0.5,
                correlation_mean=np.zeros(4),
                correlation_err=np.zeros(4),
                n_samples=5,
            )

        mock_rsp.side_effect = side_effect

        result = run_sweep(config, max_workers=1)

        # mu=0.0, mu=2.0, mu=4.0 の 3 点が試行される
        assert mock_rsp.call_count == 3
        # 2 点は成功、1 点は失敗
        assert len(result.points) == 2
        assert len(result.failed) == 1
        # 失敗ポイントのエラーメッセージを確認
        failed_U, failed_mu, failed_msg = result.failed[0]
        assert failed_U == pytest.approx(20.0)
        assert failed_mu == pytest.approx(2.0)
        assert "Fortran シミュレーション失敗" in failed_msg
        # 成功率は 2/3
        assert result.success_rate == pytest.approx(2.0 / 3.0)


# ============================================================
# 5. _run_fortran_with_progress() のテスト
# ============================================================


class TestRunFortranWithProgress:
    """_run_fortran_with_progress() のテスト群"""

    @patch("sqm.runner.subprocess.Popen")
    def test_進捗表示が正しく動作する(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """stdout から sample: 行を読み、正常終了する"""
        from sqm.config import PathConfig

        paths = PathConfig(
            output_dir=tmp_path,
            figures_dir=tmp_path / "figures",
            fortran_binary=Path("/usr/bin/true"),
        )

        # stdout をシミュレート
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = [
            b"sample: 1 / 5 0\n",
            b"sample: 2 / 5 0\n",
            b"",  # EOF
        ]
        mock_proc.returncode = 0
        mock_proc.stderr = None
        mock_popen.return_value = mock_proc

        _run_fortran_with_progress(paths, "params.dat", 20.0, 1.0, 5)

        mock_popen.assert_called_once()
        mock_proc.wait.assert_called()

    @patch("sqm.runner.subprocess.Popen")
    def test_異常終了でCalledProcessErrorを送出する(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        """Fortran が非ゼロで終了した場合に例外"""
        from subprocess import CalledProcessError

        from sqm.config import PathConfig

        paths = PathConfig(
            output_dir=tmp_path,
            figures_dir=tmp_path / "figures",
            fortran_binary=Path("/usr/bin/false"),
        )

        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = [b""]
        mock_proc.returncode = 1
        mock_proc.stderr.read.return_value = b"error"
        mock_popen.return_value = mock_proc

        with pytest.raises(CalledProcessError):
            _run_fortran_with_progress(paths, "params.dat", 20.0, 1.0, 5)

    @patch("sqm.runner.subprocess.Popen")
    def test_KeyboardInterruptでプロセスが終了される(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        """Ctrl+C 時にプロセスが terminate される"""
        from sqm.config import PathConfig

        paths = PathConfig(
            output_dir=tmp_path,
            figures_dir=tmp_path / "figures",
            fortran_binary=Path("/usr/bin/true"),
        )

        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = KeyboardInterrupt
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        with pytest.raises(KeyboardInterrupt):
            _run_fortran_with_progress(paths, "params.dat", 20.0, 1.0, 5)

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called()


# ============================================================
# 6. autocorrelation 有効パスのテスト
# ============================================================


class TestRunSinglePointAutocorrelation:
    """run_single_point() の autocorrelation 有効パスのテスト群"""

    @patch("sqm.runner.subprocess.run")
    def test_autocorrelation有効時に補正値が返される(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """skip_autocorrelation=False かつ n_samples > 20 で corrected_mean が非 None"""
        config = Config(
            simulation=SimulationConfig(Nsample=30),
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
        )

        # 30 サンプル、ランダムな値を持つバイナリファイル作成
        dat_path = tmp_path / "U=10.0,mu=1.0,s=1d0.dat"
        _create_test_binary(dat_path, Nx=4, n_samples=30, U=10.0, mu=1.0)

        mock_run.return_value = MagicMock(returncode=0)

        result = run_single_point(U=10.0, mu=1.0, config=config, skip_autocorrelation=False)

        assert result.n_samples == 30
        # n_samples > 20 かつ skip=False なので autocorrelation が実行される
        # テストバイナリのデータは単純なので thermalization_skip が小さく、
        # corrected_mean が設定される
        assert result.corrected_mean is not None
        assert result.corrected_error_val is not None
        assert result.n_eff is not None
        assert result.n_eff > 0

    @patch("sqm.runner.subprocess.run")
    def test_サンプル数が少ない場合はautocorrelationスキップ(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """n_samples <= 20 の場合は autocorrelation がスキップされる"""
        config = Config(
            simulation=SimulationConfig(Nsample=10),
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
        )

        dat_path = tmp_path / "U=10.0,mu=1.0,s=1d0.dat"
        _create_test_binary(dat_path, Nx=4, n_samples=10, U=10.0, mu=1.0)

        mock_run.return_value = MagicMock(returncode=0)

        result = run_single_point(U=10.0, mu=1.0, config=config, skip_autocorrelation=False)

        assert result.n_samples == 10
        assert result.corrected_mean is None
        assert result.n_eff is None


# ============================================================
# 7. _reset_signals() のテスト (L88)
# ============================================================


class TestResetSignals:
    """_reset_signals() のテスト群"""

    def test_SIGINTのデフォルトハンドラが復元される(self) -> None:
        """_reset_signals() が SIGINT を SIG_DFL に設定することを確認する"""
        import signal

        # 一時的に SIGINT を SIG_IGN に変更
        original = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        try:
            _reset_signals()
            handler = signal.getsignal(signal.SIGINT)
            assert handler == signal.SIG_DFL
        finally:
            # 元のハンドラに復元
            signal.signal(signal.SIGINT, original)


# ============================================================
# 8. run_single_point() の show_progress=True パス (L181)
# ============================================================


class TestRunSinglePointShowProgress:
    """run_single_point() の show_progress=True パスのテスト群"""

    @patch("sqm.runner._run_fortran_with_progress")
    def test_show_progress有効時にprogress関数が呼ばれる(
        self, mock_progress: MagicMock, tmp_path: Path
    ) -> None:
        """show_progress=True の場合、_run_fortran_with_progress が呼ばれる"""
        config = Config(
            simulation=SimulationConfig(Nsample=5),
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
        )

        # Fortran が生成するはずの偽バイナリを事前作成
        dat_path = tmp_path / "U=20.0,mu=0.5,s=1d0.dat"
        _create_test_binary(dat_path, Nx=4, n_samples=5, U=20.0, mu=0.5)

        result = run_single_point(
            U=20.0,
            mu=0.5,
            config=config,
            skip_autocorrelation=True,
            show_progress=True,
        )

        assert isinstance(result, PointResult)
        mock_progress.assert_called_once()
        # 第一引数が PathConfig であること
        call_args = mock_progress.call_args
        assert call_args[0][0] == config.paths


# ============================================================
# 9. _build_param_grid() の U スイープパス (L260-261)
# ============================================================


class TestBuildParamGrid:
    """_build_param_grid() のテスト群"""

    def test_Uスイープ時のパラメータグリッド構築(self) -> None:
        """sweep_param == 'U' の場合、mu が固定され U がスイープされる"""
        sweep = SweepConfig(mu=1.5, U_start=10.0, U_end=30.0, U_step=10.0)

        param_grid, sweep_name, fixed_value = _build_param_grid(sweep)

        assert sweep_name == "U"
        assert fixed_value == pytest.approx(1.5)
        # U=10.0, U=20.0 の 2 点
        assert len(param_grid) == 2
        # 各タプルは (U, mu) で mu=1.5 固定
        for _U_val, mu_val in param_grid:
            assert mu_val == pytest.approx(1.5)

    def test_Uスイープでmu未指定の場合はデフォルト0(self) -> None:
        """mu が None の場合、fixed_value は 0.0 になる"""
        sweep = SweepConfig(U_start=10.0, U_end=30.0, U_step=10.0)

        param_grid, sweep_name, fixed_value = _build_param_grid(sweep)

        assert sweep_name == "U"
        assert fixed_value == pytest.approx(0.0)
        for _U_val, mu_val in param_grid:
            assert mu_val == pytest.approx(0.0)


# ============================================================
# 10. _prepare_run_directory() の U スイープラベル (L276) + 既存リンク削除 (L295)
# ============================================================


class TestPrepareRunDirectory:
    """_prepare_run_directory() のテスト群"""

    def test_Uスイープ時のランディレクトリラベル(self, tmp_path: Path) -> None:
        """sweep_name='U' の場合、ディレクトリ名に sweep_U_mu が含まれる"""
        config = Config(
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
        )

        updated_config = _prepare_run_directory(config, "U", 1.5)

        run_dir = updated_config.paths.output_dir
        assert "sweep_U_mu1.5" in run_dir.name
        assert run_dir.exists()
        assert (run_dir / "figures").exists()

    def test_既存のlatestリンクが更新される(self, tmp_path: Path) -> None:
        """既に latest シンボリックリンクが存在する場合、正しく更新される"""
        config = Config(
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
        )

        # 初回: latest リンクを作成
        _prepare_run_directory(config, "mu", 20.0)
        latest_link = tmp_path / "latest"
        assert latest_link.is_symlink()
        assert latest_link.resolve().name  # 初回のターゲットが存在すること

        # 2回目: latest リンクが更新される（L295: unlink が実行される）
        updated_config = _prepare_run_directory(config, "mu", 20.0)
        assert latest_link.is_symlink()
        second_target = updated_config.paths.output_dir.name
        # latest が最新のディレクトリを指していることを確認
        assert (tmp_path / latest_link.readlink()).name == second_target


# ============================================================
# 11. _execute_sweep の KeyboardInterrupt (L358-362) + run_sweep の中断パス (L480)
# ============================================================


class _InterruptingExecutor:
    """as_completed の反復中に KeyboardInterrupt を発生させるモックエグゼキュータ。

    _execute_sweep の KeyboardInterrupt ハンドリングをテストする。
    futures 辞書は正常に構築されるが、future.result() 呼び出し時に
    KeyboardInterrupt が発生するようにする。
    """

    def __init__(self, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> _InterruptingExecutor:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def shutdown(self, *, wait: bool = True, cancel_futures: bool = False) -> None:
        pass

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:
        future: Future[Any] = Future()
        # result() 呼び出し時に KeyboardInterrupt を発生させる
        future.set_exception(KeyboardInterrupt())
        return future


class TestExecuteSweepInterrupt:
    """_execute_sweep の KeyboardInterrupt テスト群"""

    @patch("sqm.runner.plot_sweep_summary")
    @patch("sqm.runner.plot_correlation")
    @patch(
        "sqm.runner.ProcessPoolExecutor",
        new=_InterruptingExecutor,
    )
    @patch("sqm.runner.run_single_point")
    def test_KeyboardInterruptで中断フラグが立つ(
        self,
        mock_rsp: MagicMock,
        mock_plot_corr: MagicMock,
        mock_plot_summary: MagicMock,
        tmp_path: Path,
    ) -> None:
        """KeyboardInterrupt 発生時、中断パスを通り SweepResult が返される"""
        config = Config(
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
            sweep=SweepConfig(U=20.0, mu_start=0.0, mu_end=4.0, mu_step=2.0),
        )

        result = run_sweep(config, max_workers=1)

        # 中断されたので plot は呼ばれない
        mock_plot_corr.assert_not_called()
        mock_plot_summary.assert_not_called()
        # SweepResult は返される（中断パス L480）
        assert isinstance(result, SweepResult)
        assert len(result.points) == 0


# ============================================================
# 12. run_sweep の max_workers 自動決定 (L445)
# ============================================================


class TestRunSweepAutoWorkers:
    """run_sweep() の max_workers 自動決定テスト群"""

    @patch("sqm.runner.plot_sweep_summary")
    @patch("sqm.runner.plot_correlation")
    @patch(
        "sqm.runner.ProcessPoolExecutor",
        new=_SequentialExecutor,
    )
    @patch("sqm.runner.run_single_point")
    def test_max_workers未指定時に自動決定される(
        self,
        mock_rsp: MagicMock,
        mock_plot_corr: MagicMock,
        mock_plot_summary: MagicMock,
        tmp_path: Path,
    ) -> None:
        """max_workers=None の場合、自動的にワーカー数が決定される"""
        config = Config(
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
            sweep=SweepConfig(U=20.0, mu_start=0.0, mu_end=4.0, mu_step=2.0),
        )

        def side_effect(U: float, mu: float, cfg: Config, **kwargs: object) -> PointResult:
            return PointResult(
                U=U,
                mu=mu,
                correlation_midpoint=0.5,
                correlation_mean=np.zeros(4),
                correlation_err=np.zeros(4),
                n_samples=5,
            )

        mock_rsp.side_effect = side_effect

        # max_workers=None で呼び出す（L445 をカバー）
        result = run_sweep(config, max_workers=None)

        assert isinstance(result, SweepResult)
        assert len(result.points) == 2
        assert mock_rsp.call_count == 2


# ============================================================
# 13. run_sweep で U スイープ実行 (L260-261, L276 の統合テスト)
# ============================================================


class TestRunSweepUSweep:
    """run_sweep() の U スイープパスの統合テスト群"""

    @patch("sqm.runner.plot_sweep_summary")
    @patch("sqm.runner.plot_correlation")
    @patch(
        "sqm.runner.ProcessPoolExecutor",
        new=_SequentialExecutor,
    )
    @patch("sqm.runner.run_single_point")
    def test_Uスイープが正しく実行される(
        self,
        mock_rsp: MagicMock,
        mock_plot_corr: MagicMock,
        mock_plot_summary: MagicMock,
        tmp_path: Path,
    ) -> None:
        """U をスイープし mu を固定した場合のエンドツーエンドテスト"""
        config = Config(
            paths=PathConfig(
                output_dir=tmp_path,
                figures_dir=tmp_path / "figures",
                fortran_binary=Path("/usr/bin/true"),
            ),
            sweep=SweepConfig(mu=1.0, U_start=10.0, U_end=30.0, U_step=10.0),
        )

        def side_effect(U: float, mu: float, cfg: Config, **kwargs: object) -> PointResult:
            return PointResult(
                U=U,
                mu=mu,
                correlation_midpoint=1.0 / (1.0 + U),
                correlation_mean=np.zeros(4),
                correlation_err=np.zeros(4),
                n_samples=5,
            )

        mock_rsp.side_effect = side_effect

        result = run_sweep(config, max_workers=1)

        # U=10.0, U=20.0 の 2 点
        assert len(result.points) == 2
        assert mock_rsp.call_count == 2
        # mu は固定値 1.0
        for pt in result.points:
            assert pt.mu == pytest.approx(1.0)
        # U 昇順にソートされている
        assert result.points[0].U <= result.points[1].U
