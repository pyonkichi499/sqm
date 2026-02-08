"""実行エンジンモジュール

パラメータスイープの並列実行、解析、プロット生成、実験ログ記録を統合する。
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import numpy as np
import numpy.typing as npt

from sqm.analysis import (
    compute_correlation,
    corrected_error,
    detect_thermalization,
    effective_sample_size,
)
from sqm.config import Config, PathConfig, SweepConfig
from sqm.experiment_log import ExperimentLog
from sqm.fortran_io import read_dat, write_params
from sqm.plotting import plot_correlation, plot_sweep_summary

logger = logging.getLogger(__name__)


# =============================================================================
# データ構造
# =============================================================================


@dataclass
class PointResult:
    """1つの (U, mu) パラメータ点の結果"""

    U: float
    mu: float
    correlation_midpoint: float
    correlation_mean: npt.NDArray[np.float64]
    correlation_err: npt.NDArray[np.float64]
    corrected_mean: float | None = None
    corrected_error_val: float | None = None
    n_eff: float | None = None
    Ntau: int = 6
    thermalization_skip: int = 0
    n_samples: int = 0
    dat_filepath: Path = field(default_factory=lambda: Path("."))


@dataclass
class SweepResult:
    """パラメータスイープ全体の結果"""

    points: list[PointResult] = field(default_factory=list)
    failed: list[tuple[float, float, str]] = field(default_factory=list)
    config: Config = field(default_factory=Config)
    walltime_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """成功率を返す (0.0 ~ 1.0)"""
        total = len(self.points) + len(self.failed)
        if total == 0:
            return 0.0
        return len(self.points) / total


# =============================================================================
# 単一パラメータ点の実行
# =============================================================================


def _reset_signals() -> None:
    """Fortran サブプロセスで SIGINT のデフォルト動作を復元する。

    ProcessPoolExecutor のワーカーは SIGINT を SIG_IGN に設定するが、
    fork した子プロセス (Fortran) もこれを継承してしまうため、
    Ctrl+C で Fortran が停止しなくなる。preexec_fn で復元する。
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def _run_fortran_with_progress(
    paths: PathConfig,
    params_filename: str,
    U: float,
    mu: float,
    nsample: int,
) -> None:
    """Fortran を実行し、サンプル進捗を1行で表示する。"""
    env = {**os.environ, "GFORTRAN_UNBUFFERED_ALL": "1"}
    label = f"  U={U:.1f}, mu={mu:.1f}"
    proc = subprocess.Popen(
        [str(paths.fortran_binary), params_filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(paths.output_dir),
        env=env,
        preexec_fn=_reset_signals,
    )
    assert proc.stdout is not None
    try:
        for raw_line in iter(proc.stdout.readline, b""):
            line = raw_line.decode().strip()
            if line.startswith("sample:"):
                parts = line.split()
                current = parts[1]
                print(f"\r{label}: sample {current}/{nsample}", end="", flush=True)
        print(flush=True)
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
        raise
    proc.wait()
    if proc.returncode != 0:
        stderr_out = proc.stderr.read().decode() if proc.stderr else ""
        raise subprocess.CalledProcessError(proc.returncode, proc.args, stderr=stderr_out)


def run_single_point(
    U: float,
    mu: float,
    config: Config,
    *,
    skip_autocorrelation: bool = False,
    show_progress: bool = False,
) -> PointResult:
    """1つの (U, mu) 点でシミュレーションを実行し解析結果を返す。

    Parameters
    ----------
    U : float
        相互作用パラメータ
    mu : float
        化学ポテンシャル
    config : Config
        シミュレーション設定
    skip_autocorrelation : bool
        True の場合、自己相関解析をスキップする
    show_progress : bool
        True の場合、Fortran のサンプル進捗をターミナルに表示する

    Returns
    -------
    PointResult
        シミュレーション結果
    """
    sim = config.simulation
    paths = config.paths

    dat_filename = f"U={U},mu={mu},s={sim.s_end}.dat"
    dat_filepath = paths.output_dir / dat_filename
    params_filename = f"params_U={U}_mu={mu}.dat"
    params_filepath = paths.output_dir / params_filename

    # 1. パラメータファイル作成
    seed = config.seed.get_seed(process_id=0) if config.seed else None
    write_params(
        mu=mu,
        U=U,
        Nsample=sim.Nsample,
        filename=dat_filename,
        paramsfile=params_filepath,
        dtau=sim.dtau,
        ds=sim.ds,
        s_end=sim.s_end,
        seed=seed,
    )

    # 2. Fortran シミュレーション実行 (cwd を output_dir に設定し相対パスで渡す)
    try:
        if show_progress:
            _run_fortran_with_progress(paths, params_filename, U, mu, sim.Nsample)
        else:
            print(f"  U={U:.1f}, mu={mu:.1f}: running ({sim.Nsample} samples)...", flush=True)
            subprocess.run(
                [str(paths.fortran_binary), params_filename],
                check=True,
                capture_output=True,
                cwd=str(paths.output_dir),
                preexec_fn=_reset_signals,
            )
    finally:
        # パラメータファイルは常に削除
        if params_filepath.exists():
            params_filepath.unlink()

    # 3. バイナリ読み込み
    header, body = read_dat(dat_filepath)
    a_list = [b["a"] for b in body]
    a_ast_list = [b["a_ast"] for b in body]
    Nx = int(header[0]["Nx"])
    Ntau = int(header[0]["Ntau"])
    n_samples = len(body)

    # 4. 相関関数計算
    corr_mean, corr_err = compute_correlation(a_list, a_ast_list, Nx)

    # 5. autocorrelation 解析
    corrected_mean_val: float | None = None
    corrected_error_val: float | None = None
    n_eff: float | None = None
    therm_skip = 0

    if not skip_autocorrelation and n_samples > 20:
        # 格子中央の相関時系列を抽出
        mid = Nx // 2
        midpoint_series = np.array(
            [np.real(a_list[i][0] * a_ast_list[i][mid]) for i in range(n_samples)]
        )

        therm_skip = detect_thermalization(midpoint_series)
        if therm_skip < n_samples - 10:
            trimmed = midpoint_series[therm_skip:]
            corrected_mean_val, corrected_error_val = corrected_error(trimmed)
            n_eff = effective_sample_size(trimmed)

    logger.info("U=%.1f, mu=%.1f 完了 (samples=%d, skip=%d)", U, mu, n_samples, therm_skip)

    return PointResult(
        U=U,
        mu=mu,
        correlation_midpoint=float(corr_mean[Nx // 2]),
        correlation_mean=corr_mean,
        correlation_err=corr_err,
        corrected_mean=corrected_mean_val,
        corrected_error_val=corrected_error_val,
        n_eff=n_eff,
        Ntau=Ntau,
        thermalization_skip=therm_skip,
        n_samples=n_samples,
        dat_filepath=dat_filepath,
    )


# =============================================================================
# パラメータスイープの実行
# =============================================================================


def _build_param_grid(
    sweep: SweepConfig,
) -> tuple[list[tuple[float, float]], str, float]:
    """スイープ設定からパラメータグリッド、スイープ名、固定値を構築する。"""
    sweep_values = sweep.sweep_values()
    sweep_name = sweep.sweep_param

    if sweep_name == "mu":
        fixed_value = sweep.U if sweep.U is not None else 0.0
        param_grid = [(fixed_value, mu_val) for mu_val in sweep_values]
    else:
        fixed_value = sweep.mu if sweep.mu is not None else 0.0
        param_grid = [(U_val, fixed_value) for U_val in sweep_values]

    return param_grid, sweep_name, fixed_value


def _prepare_run_directory(
    config: Config,
    sweep_name: str,
    fixed_value: float,
) -> Config:
    """タイムスタンプ付きランディレクトリを作成し、config を差し替えて返す。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if sweep_name == "mu":
        run_label = f"sweep_mu_U{fixed_value:.1f}"
    else:
        run_label = f"sweep_U_mu{fixed_value:.1f}"

    run_dir = config.paths.output_dir / f"{timestamp}_{run_label}"
    figures_dir = run_dir / "figures"

    run_paths = PathConfig(
        output_dir=run_dir,
        figures_dir=figures_dir,
        fortran_binary=config.paths.fortran_binary,
    )
    config = replace(config, paths=run_paths)

    run_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    config.to_yaml(run_dir / "config.yaml")

    # latest シンボリックリンクを更新
    latest_link = run_dir.parent / "latest"
    if latest_link.is_symlink() or latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(run_dir.name)

    return config


def _execute_sweep(
    param_grid: list[tuple[float, float]],
    config: Config,
    exp_log: ExperimentLog,
    *,
    skip_autocorrelation: bool,
    max_workers: int,
) -> tuple[list[PointResult], list[tuple[float, float, str]], bool]:
    """パラメータグリッドを並列実行し、結果リスト・失敗リスト・中断フラグを返す。"""
    points: list[PointResult] = []
    failed: list[tuple[float, float, str]] = []
    total = len(param_grid)
    completed = 0
    sweep_start = time.monotonic()
    show_progress = max_workers == 1
    interrupted = False

    executor = ProcessPoolExecutor(max_workers=max_workers)
    try:
        futures = {
            executor.submit(
                run_single_point,
                U,
                mu,
                config,
                skip_autocorrelation=skip_autocorrelation,
                show_progress=show_progress,
            ): (U, mu)
            for U, mu in param_grid
        }
        for future in as_completed(futures):
            U, mu = futures[future]
            completed += 1
            elapsed = time.monotonic() - sweep_start
            try:
                result = future.result()
                points.append(result)
                print(
                    f"  [{completed}/{total}] U={U:.1f}, mu={mu:.1f}"
                    f" done ({result.n_samples} samples, {elapsed:.1f}s elapsed)",
                    flush=True,
                )
                exp_log.add_result(
                    f"U={U}_mu={mu}",
                    correlation=result.correlation_midpoint,
                    n_samples=result.n_samples,
                    n_eff=result.n_eff,
                    thermalization_skip=result.thermalization_skip,
                )
            except Exception as e:
                failed.append((U, mu, str(e)))
                print(
                    f"  [{completed}/{total}] U={U:.1f}, mu={mu:.1f}"
                    f" FAILED ({elapsed:.1f}s elapsed)",
                    flush=True,
                )
                logger.error("U=%.1f, mu=%.1f 失敗: %s", U, mu, e)
    except KeyboardInterrupt:
        print("\n中断しました。子プロセスを停止中...", flush=True)
        for f in futures:
            f.cancel()
        interrupted = True
    finally:
        executor.shutdown(wait=not interrupted, cancel_futures=interrupted)

    return points, failed, interrupted


def _generate_plots(
    points: list[PointResult],
    sweep_name: str,
    fixed_value: float,
    config: Config,
) -> None:
    """各ポイントの相関プロットとスイープサマリープロットを生成する。"""
    for pt in points:
        Nx = len(pt.correlation_mean)
        xarr = np.arange(Nx, dtype=np.float64)
        savepath = config.paths.figures_dir / f"mu={pt.mu:.1f},U={pt.U:.1f},N={pt.n_samples}.png"
        plot_correlation(
            xarr,
            pt.correlation_mean,
            pt.correlation_err,
            mu=pt.mu,
            U=pt.U,
            Ntau=pt.Ntau,
            N=pt.n_samples,
            savepath=savepath,
        )

    fixed_name = "U" if sweep_name == "mu" else "mu"
    corr_values = [pt.correlation_midpoint for pt in points]
    sweep_arr = np.array([pt.mu if sweep_name == "mu" else pt.U for pt in points])
    summary_path = config.paths.figures_dir / "sweep_summary.png"
    plot_sweep_summary(
        sweep_arr,
        corr_values,
        sweep_name,
        fixed_name,
        fixed_value,
        config.simulation.Nsample,
        summary_path,
    )


def run_sweep(
    config: Config,
    *,
    skip_autocorrelation: bool = False,
    max_workers: int | None = None,
) -> SweepResult:
    """パラメータスイープを並列実行し結果を返す。

    Parameters
    ----------
    config : Config
        シミュレーション設定（sweep が必須）
    skip_autocorrelation : bool
        True の場合、自己相関解析をスキップする
    max_workers : int | None
        並列ワーカー数。None の場合は自動決定。

    Returns
    -------
    SweepResult
        スイープ結果

    Raises
    ------
    ValueError
        config.sweep が None の場合
    """
    if config.sweep is None:
        raise ValueError("スイープ設定が必要です (config.sweep is None)")

    # 1. パラメータグリッド構築
    sweep_cfg = config.sweep
    param_grid, sweep_name, fixed_value = _build_param_grid(sweep_cfg)

    # 2. ランディレクトリ作成 + config 差し替え
    config = _prepare_run_directory(config, sweep_name, fixed_value)

    # 3. ワーカー数
    if max_workers is None:
        max_workers = min(len(param_grid), os.cpu_count() or 1)

    # 4. 実験ログ開始
    exp_log = ExperimentLog()
    exp_log.start_timer()
    exp_log.capture_git_info()
    exp_log.capture_environment()
    exp_log.set_parameters(
        sweep_param=sweep_name,
        sweep_values=sweep_cfg.sweep_values(),
        Nsample=config.simulation.Nsample,
        dtau=config.simulation.dtau,
        ds=config.simulation.ds,
        s_end=config.simulation.s_end,
    )

    logger.info(
        "スイープ開始: %s (%d 点), %d workers",
        sweep_name,
        len(param_grid),
        max_workers,
    )

    # 5. 並列実行
    points, failed, interrupted = _execute_sweep(
        param_grid,
        config,
        exp_log,
        skip_autocorrelation=skip_autocorrelation,
        max_workers=max_workers,
    )

    exp_log.stop_timer()

    if interrupted:
        return SweepResult(
            points=points,
            failed=failed,
            config=config,
            walltime_seconds=exp_log.walltime_seconds,
        )

    # 6. プロット生成
    points.sort(key=lambda p: p.mu if sweep_name == "mu" else p.U)
    _generate_plots(points, sweep_name, fixed_value, config)

    # 7. 実験ログ保存
    log_path = config.paths.output_dir / "experiment_log.json"
    exp_log.save_json(log_path)
    logger.info("実験ログ保存: %s", log_path)

    return SweepResult(
        points=points,
        failed=failed,
        config=config,
        walltime_seconds=exp_log.walltime_seconds,
    )
