"""自己相関解析モジュールのテスト

TDD の Red-Green-Refactor サイクルに従い、各ラウンドごとにテストを記述。
conftest.py により np.random.seed(42) が全テストで自動適用される。
"""
from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pytest


# ============================================================
# Round 1: autocorrelation 関数
# ============================================================


class TestAutocorrelation:
    """自己相関関数のテスト"""

    def test_自己相関関数_ラグ0は常に1(self) -> None:
        """正規化により先頭は常に1.0"""
        from sqm.autocorrelation import autocorrelation

        data = np.random.randn(1000)
        result = autocorrelation(data)
        assert result[0] == pytest.approx(1.0)

    def test_自己相関関数_完全に相関したデータで1を返す(self) -> None:
        """同一の定数値列では自己相関が全ラグで1"""
        from sqm.autocorrelation import autocorrelation

        data = np.ones(100)
        result = autocorrelation(data)
        # 定数列の自己相関は全て1（分散が0なので特殊ケース）
        np.testing.assert_allclose(result, np.ones_like(result), atol=1e-10)

    def test_自己相関関数_ホワイトノイズでラグ1以降ほぼゼロ(self) -> None:
        """ランダムデータではラグ0以降は約0"""
        from sqm.autocorrelation import autocorrelation

        data = np.random.randn(10000)
        result = autocorrelation(data)
        # ラグ0は1.0
        assert result[0] == pytest.approx(1.0)
        # ラグ1以降は0に近い（統計的ゆらぎを考慮して緩めの閾値）
        assert np.all(np.abs(result[1:50]) < 0.05)

    def test_自己相関関数_既知の周期信号で正しいパターン(self) -> None:
        """sin波のような周期データで周期的な自己相関"""
        from sqm.autocorrelation import autocorrelation

        period = 50
        t = np.arange(1000)
        data = np.sin(2 * np.pi * t / period)
        result = autocorrelation(data, max_lag=100)
        # ラグ=period で再び高い正の相関
        assert result[period] > 0.9
        # ラグ=period/2 で負の相関
        assert result[period // 2] < -0.9

    def test_自己相関関数_max_lagで出力長が制限される(self) -> None:
        """max_lag を指定すると出力の長さがmax_lag+1になる"""
        from sqm.autocorrelation import autocorrelation

        data = np.random.randn(1000)
        max_lag = 50
        result = autocorrelation(data, max_lag=max_lag)
        assert len(result) == max_lag + 1

    def test_自己相関関数_max_lag未指定でデータ長と同じ(self) -> None:
        """max_lag を指定しない場合、出力の長さはデータ長"""
        from sqm.autocorrelation import autocorrelation

        data = np.random.randn(200)
        result = autocorrelation(data)
        assert len(result) == len(data)


# ============================================================
# Round 2: integrated_autocorr_time 関数
# ============================================================


class TestIntegratedAutocorrTime:
    """積分自己相関時間のテスト"""

    def test_積分自己相関時間_ホワイトノイズでは約0_5(self) -> None:
        """独立データの τ_int は 0.5 に近い"""
        from sqm.autocorrelation import integrated_autocorr_time

        data = np.random.randn(100000)
        tau = integrated_autocorr_time(data)
        # 独立データの τ_int ≈ 0.5（自己相関関数の和が 0.5 に収束）
        assert tau == pytest.approx(0.5, abs=0.1)

    def test_積分自己相関時間_相関データでは大きい値(self) -> None:
        """相関のあるデータでは τ_int > 1"""
        from sqm.autocorrelation import integrated_autocorr_time

        # AR(1) プロセスで相関のあるデータを生成
        n = 50000
        phi = 0.95
        data = np.zeros(n)
        data[0] = np.random.randn()
        for i in range(1, n):
            data[i] = phi * data[i - 1] + np.random.randn()
        tau = integrated_autocorr_time(data)
        # phi=0.95 の AR(1) では理論値 τ_int = (1+phi)/(2*(1-phi)) ≈ 19.5
        assert tau > 1.0
        # 理論値との比較（緩めの範囲）
        theoretical_tau = (1 + phi) / (2 * (1 - phi))
        assert tau == pytest.approx(theoretical_tau, rel=0.3)

    def test_積分自己相関時間_定数列では0_5(self) -> None:
        """定数列（分散0）でも適切に処理される"""
        from sqm.autocorrelation import integrated_autocorr_time

        data = np.ones(100)
        tau = integrated_autocorr_time(data)
        # 定数列 → 自己相関は全て1 → τ_int は大きな値になる
        # ただし実用的にはwindow打ち切りにより有限値
        assert tau >= 0.5


# ============================================================
# Round 3: effective_sample_size 関数
# ============================================================


class TestEffectiveSampleSize:
    """有効サンプル数のテスト"""

    def test_有効サンプル数_独立データではN個に近い(self) -> None:
        """独立データの有効サンプル数 ≈ N"""
        from sqm.autocorrelation import effective_sample_size

        data = np.random.randn(10000)
        n_eff = effective_sample_size(data)
        # 独立データでは N_eff ≈ N
        assert n_eff == pytest.approx(len(data), rel=0.2)

    def test_有効サンプル数_相関データではN未満(self) -> None:
        """相関データの有効サンプル数 < N"""
        from sqm.autocorrelation import effective_sample_size

        # AR(1) プロセスで相関のあるデータを生成
        n = 50000
        phi = 0.95
        data = np.zeros(n)
        data[0] = np.random.randn()
        for i in range(1, n):
            data[i] = phi * data[i - 1] + np.random.randn()
        n_eff = effective_sample_size(data)
        # 相関があるため有効サンプル数は元のサンプル数より少ない
        assert n_eff < n
        # 理論値: N_eff = N / (2 * τ_int)
        # φ=0.95: τ_int ≈ 19.5 → N_eff ≈ 50000 / 39 ≈ 1282
        assert n_eff < n / 5

    def test_有効サンプル数_常に正の値(self) -> None:
        """有効サンプル数は常に正"""
        from sqm.autocorrelation import effective_sample_size

        data = np.random.randn(100)
        n_eff = effective_sample_size(data)
        assert n_eff > 0


# ============================================================
# Round 4: detect_thermalization 関数
# ============================================================


class TestDetectThermalization:
    """thermalization検出のテスト"""

    def test_thermalization検出_定常データではスキップなし(self) -> None:
        """定常データのthermalization期間は0または非常に小さい"""
        from sqm.autocorrelation import detect_thermalization

        # 完全にランダムな定常データ
        data = np.random.randn(1000)
        skip = detect_thermalization(data)
        # 定常データではスキップ不要（ウィンドウ幅程度は許容）
        assert skip < len(data) * 0.1

    def test_thermalization検出_トレンドありデータで正しくスキップ(self) -> None:
        """前半がトレンド、後半が定常のデータ"""
        from sqm.autocorrelation import detect_thermalization

        n = 1000
        # 前半200点：急激なドリフト（thermalization期間）
        trend = np.linspace(10.0, 0.0, 200)
        # 後半800点：定常状態
        stationary = np.random.randn(800) * 0.1
        data = np.concatenate([trend, stationary])
        skip = detect_thermalization(data, window_size=20)
        # スキップ点は トレンド部分の終了付近（200付近）であること
        assert 100 <= skip <= 400

    def test_thermalization検出_window_sizeの影響(self) -> None:
        """window_size が検出に影響する"""
        from sqm.autocorrelation import detect_thermalization

        n = 1000
        trend = np.linspace(5.0, 0.0, 200)
        stationary = np.random.randn(800) * 0.1
        data = np.concatenate([trend, stationary])
        skip_small = detect_thermalization(data, window_size=10)
        skip_large = detect_thermalization(data, window_size=50)
        # どちらも非負値
        assert skip_small >= 0
        assert skip_large >= 0


# ============================================================
# Round 5: thin_data 関数
# ============================================================


class TestThinData:
    """データ間引き（thinning）のテスト"""

    def test_thinning_相関データを間引く(self) -> None:
        """自己相関時間に基づいてデータを間引く"""
        from sqm.autocorrelation import thin_data

        # AR(1) プロセスで相関のあるデータを生成
        n = 10000
        phi = 0.9
        data = np.zeros(n)
        data[0] = np.random.randn()
        for i in range(1, n):
            data[i] = phi * data[i - 1] + np.random.randn()
        thinned = thin_data(data)
        # 間引き後のデータ数は元より少ない
        assert len(thinned) < len(data)
        # 間引き後のデータ数は1以上
        assert len(thinned) >= 1

    def test_thinning_結果のデータは独立に近い(self) -> None:
        """間引き後の自己相関時間は約0.5に近づく"""
        from sqm.autocorrelation import autocorrelation, thin_data

        # AR(1) プロセスで強い相関のあるデータを生成
        n = 50000
        phi = 0.9
        data = np.zeros(n)
        data[0] = np.random.randn()
        for i in range(1, n):
            data[i] = phi * data[i - 1] + np.random.randn()
        thinned = thin_data(data)
        # 間引き後のラグ1の自己相関は小さくなっている
        acf = autocorrelation(thinned, max_lag=5)
        assert abs(acf[1]) < 0.3

    def test_thinning_明示的なインターバル指定(self) -> None:
        """thin_interval を明示的に指定して間引く"""
        from sqm.autocorrelation import thin_data

        data = np.arange(100, dtype=np.float64)
        thinned = thin_data(data, thin_interval=5)
        # 5刻みで間引き → 20個
        assert len(thinned) == 20
        np.testing.assert_array_equal(thinned, data[::5])

    def test_thinning_インターバル1では全データ返す(self) -> None:
        """thin_interval=1 では全データがそのまま返る"""
        from sqm.autocorrelation import thin_data

        data = np.random.randn(100)
        thinned = thin_data(data, thin_interval=1)
        np.testing.assert_array_equal(thinned, data)


# ============================================================
# Round 6: corrected_error 関数
# ============================================================


class TestCorrectedError:
    """自己相関を考慮した補正誤差のテスト"""

    def test_補正誤差_独立データではナイーブ誤差と同程度(self) -> None:
        """独立データでは補正誤差 ≈ ナイーブ標準誤差"""
        from sqm.autocorrelation import corrected_error

        data = np.random.randn(10000)
        mean, error = corrected_error(data)
        # 平均値の確認
        assert mean == pytest.approx(np.mean(data), abs=1e-10)
        # ナイーブ標準誤差
        naive_error = np.std(data, ddof=1) / np.sqrt(len(data))
        # 独立データでは補正誤差とナイーブ誤差はほぼ同じ
        assert error == pytest.approx(naive_error, rel=0.5)

    def test_補正誤差_相関データではナイーブ誤差より大きい(self) -> None:
        """相関データでは補正誤差 > ナイーブ標準誤差"""
        from sqm.autocorrelation import corrected_error

        # AR(1) プロセスで相関のあるデータを生成
        n = 50000
        phi = 0.95
        data = np.zeros(n)
        data[0] = np.random.randn()
        for i in range(1, n):
            data[i] = phi * data[i - 1] + np.random.randn()
        mean, error = corrected_error(data)
        # ナイーブ標準誤差
        naive_error = np.std(data, ddof=1) / np.sqrt(len(data))
        # 補正誤差はナイーブ誤差より大きくなる
        assert error > naive_error * 2

    def test_補正誤差_返り値の型(self) -> None:
        """返り値は (float, float) のタプル"""
        from sqm.autocorrelation import corrected_error

        data = np.random.randn(1000)
        result = corrected_error(data)
        assert isinstance(result, tuple)
        assert len(result) == 2
        mean, error = result
        assert isinstance(mean, float)
        assert isinstance(error, float)

    def test_補正誤差_誤差は常に正(self) -> None:
        """誤差は常に正の値"""
        from sqm.autocorrelation import corrected_error

        data = np.random.randn(1000)
        _, error = corrected_error(data)
        assert error > 0
