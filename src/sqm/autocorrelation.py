"""自己相関解析モジュール

Monte Carlo / Langevin シミュレーションデータの自己相関を解析し、
正しい統計的誤差推定を行うためのツールを提供する。

主な機能:
- autocorrelation: 自己相関関数の計算
- integrated_autocorr_time: 積分自己相関時間の計算
- effective_sample_size: 有効サンプル数の計算
- detect_thermalization: thermalization 期間の検出
- thin_data: データの間引き
- corrected_error: 自己相関を考慮した補正済み誤差推定
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def autocorrelation(
    data: npt.NDArray[np.float64],
    max_lag: int | None = None,
) -> npt.NDArray[np.float64]:
    """自己相関関数を計算する（正規化済み、ラグ0=1）。

    FFT を用いて効率的に正規化自己相関関数を計算する。
    定数列（分散0）の場合は全ラグで 1.0 を返す。

    Args:
        data: 1次元の時系列データ。
        max_lag: 計算する最大ラグ。None の場合はデータ長 - 1。
            出力の長さは max_lag + 1（ラグ0 を含む）。
            max_lag が None の場合は出力の長さはデータ長。

    Returns:
        正規化自己相関関数の配列。インデックス k がラグ k に対応。
    """
    n = len(data)
    if max_lag is None:
        max_lag = n - 1

    mean = np.mean(data)
    var = np.var(data)

    # 分散0（定数列）の場合は全て1を返す
    if var == 0.0:
        return np.ones(max_lag + 1, dtype=np.float64)

    # 平均を引いた系列
    x = data - mean

    # FFT を用いた自己相関の計算
    # zero-padding して循環相関を避ける
    fft_size = 2 * n
    fft_x = np.fft.fft(x, n=fft_size)
    acf_full = np.fft.ifft(fft_x * np.conj(fft_x)).real[:n]

    # 正規化: ラグ0で割る（= N * var）
    acf_full /= acf_full[0]

    return acf_full[: max_lag + 1].copy()


def _auto_window(tau_cumsum: npt.NDArray[np.float64]) -> int:
    """Sokal の自動ウィンドウ法で打ち切りラグを決定する。

    累積和が c * tau を超えたラグで打ち切る。
    Sokal (1997) の推奨値 c=5 を使用。

    Args:
        tau_cumsum: 積分自己相関時間の累積和（各ラグまでの部分和）。

    Returns:
        打ち切りラグのインデックス。
    """
    c = 5.0
    for m in range(1, len(tau_cumsum)):
        if m >= c * tau_cumsum[m]:
            return m
    # 条件を満たさない場合はデータ長の半分で打ち切り
    return len(tau_cumsum) - 1


def integrated_autocorr_time(
    data: npt.NDArray[np.float64],
) -> float:
    """積分自己相関時間 τ_int を計算する。

    Sokal の自動ウィンドウ法を用いて自己相関関数の和を
    適切なラグで打ち切り、積分自己相関時間を推定する。

    τ_int = 0.5 + Σ_{k=1}^{M} ρ(k)

    独立データの場合、ρ(k≥1) ≈ 0 なので τ_int ≈ 0.5。
    相関のあるデータでは τ_int > 0.5。

    Args:
        data: 1次元の時系列データ。

    Returns:
        積分自己相関時間 τ_int。
    """
    n = len(data)
    max_lag = min(n - 1, n // 2)
    acf = autocorrelation(data, max_lag=max_lag)

    # τ_int の累積和を計算: τ_int(M) = 0.5 + Σ_{k=1}^{M} ρ(k)
    tau_cumsum = 0.5 + np.cumsum(acf[1:])

    # 自動ウィンドウで打ち切りラグを決定
    window = _auto_window(tau_cumsum)

    return float(tau_cumsum[window - 1]) if window >= 1 else 0.5


def effective_sample_size(
    data: npt.NDArray[np.float64],
) -> float:
    """有効サンプル数 N_eff = N / (2 * τ_int) を計算する。

    自己相関のあるデータでは、実質的に独立なサンプルの数は
    元のサンプル数 N よりも少なくなる。有効サンプル数は
    この独立サンプル数の推定値である。

    Args:
        data: 1次元の時系列データ。

    Returns:
        有効サンプル数 N_eff。常に正の値。
    """
    n = len(data)
    tau = integrated_autocorr_time(data)
    n_eff = n / (2.0 * tau)
    # 有効サンプル数は最低でも1
    return max(1.0, n_eff)


def detect_thermalization(
    data: npt.NDArray[np.float64],
    window_size: int = 10,
) -> int:
    """thermalization 期間を検出し、スキップすべきサンプル数を返す。

    Geweke 診断に着想を得た手法：データを先頭からスライドさせた
    ウィンドウの平均値と、後半（定常と仮定する）部分の平均値を比較し、
    連続する複数のウィンドウの平均が定常状態の範囲内に入った
    最初の位置を thermalization の終了点とする。

    Args:
        data: 1次元の時系列データ。
        window_size: 移動平均のウィンドウサイズ。

    Returns:
        スキップすべきサンプル数（0-indexed）。
        定常データでは0に近い値。
    """
    n = len(data)
    if n < 2 * window_size:
        return 0

    # 移動平均を計算
    n_windows = n // window_size
    if n_windows < 3:
        return 0

    window_means = np.array(
        [np.mean(data[i * window_size : (i + 1) * window_size]) for i in range(n_windows)]
    )

    # 後半のウィンドウ平均から定常状態の統計を推定
    # 後半の50%を定常状態と仮定
    stationary_start = n_windows // 2
    stationary_means = window_means[stationary_start:]
    stationary_mean = np.mean(stationary_means)
    stationary_std = np.std(stationary_means)

    # 定常状態からの偏差を計算
    deviations = np.abs(window_means - stationary_mean)

    # 閾値を設定（定常状態の平均から3σ以内に入っていれば定常とみなす）
    threshold = 1e-10 if stationary_std < 1e-15 else 3.0 * stationary_std

    # 連続するウィンドウ数（少なくとも3つ連続で閾値内なら定常と判断）
    n_consecutive = min(3, n_windows // 3)

    # 最初に n_consecutive 個連続で閾値内のウィンドウを探す
    for i in range(n_windows - n_consecutive + 1):
        block = deviations[i : i + n_consecutive]
        if np.all(block <= threshold):
            return i * window_size

    # 見つからない場合は後半の開始点を返す
    return stationary_start * window_size


def thin_data(
    data: npt.NDArray[np.float64],
    thin_interval: int | None = None,
) -> npt.NDArray[np.float64]:
    """データを自己相関時間に基づいて間引く。

    thin_interval が指定されていない場合、積分自己相関時間を
    自動計算して間引き間隔を決定する。

    Args:
        data: 1次元の時系列データ。
        thin_interval: 間引き間隔。None の場合は自動計算。

    Returns:
        間引き後のデータ配列。
    """
    if thin_interval is None:
        tau = integrated_autocorr_time(data)
        # 間引き間隔は 2 * τ_int（切り上げ、最低1）
        thin_interval = max(1, int(np.ceil(2.0 * tau)))

    return data[::thin_interval].copy()


def corrected_error(
    data: npt.NDArray[np.float64],
) -> tuple[float, float]:
    """自己相関を考慮した補正済みの平均と誤差を返す。

    標準的な標準誤差 σ/√N は、データが独立であることを仮定している。
    自己相関がある場合、真の誤差は σ/√N_eff = σ * √(2τ_int/N) となる。

    これは σ/√N に √(2τ_int) を掛けたものに等しい。

    Args:
        data: 1次元の時系列データ。

    Returns:
        (mean, error) のタプル。
        mean: データの平均値。
        error: 自己相関を考慮した補正済み標準誤差。
    """
    n = len(data)
    mean = float(np.mean(data))
    var = float(np.var(data, ddof=1))
    tau = integrated_autocorr_time(data)

    # 補正済み誤差: σ * √(2τ_int / N)
    error = float(np.sqrt(var * 2.0 * tau / n))

    return (mean, error)
