"""collect.py のテスト"""
import os
import struct
import numpy as np
import pytest
import matplotlib
matplotlib.use("Agg")

import collect


def _make_binary_dat(path, Nx, U, mu, Ntau, samples):
    """テスト用のFortranバイナリ .dat ファイルを作成"""
    with open(path, 'wb') as f:
        header_size = 4 + 8 + 8 + 4
        f.write(struct.pack('<i', header_size))
        f.write(struct.pack('<i', Nx))
        f.write(struct.pack('<d', U))
        f.write(struct.pack('<d', mu))
        f.write(struct.pack('<i', Ntau))
        f.write(struct.pack('<i', header_size))
        body_size = Nx * 16 + Nx * 16
        for a, a_ast in samples:
            f.write(struct.pack('<i', body_size))
            for c in a:
                f.write(struct.pack('<dd', c.real, c.imag))
            for c in a_ast:
                f.write(struct.pack('<dd', c.real, c.imag))
            f.write(struct.pack('<i', body_size))


def _make_test_dat(outdir, U, mu, Nx=4, Nsample=10):
    """outdir に U=...,mu=... 形式のテストファイルを作成"""
    fname = f"U={U},mu={mu}.dat"
    rng = np.random.default_rng(int(U * 100 + mu * 10))
    samples = []
    for _ in range(Nsample):
        a = rng.standard_normal(Nx) + 1j * rng.standard_normal(Nx)
        a_ast = rng.standard_normal(Nx) + 1j * rng.standard_normal(Nx)
        samples.append((a, a_ast))
    _make_binary_dat(os.path.join(outdir, fname), Nx, U, mu, 100, samples)
    return fname


class TestAnalyzeOne:
    def test_returns_mean_and_err(self, tmp_path):
        """戻り値が (mean, err) のタプル"""
        _make_test_dat(str(tmp_path), U=10.0, mu=5.0)
        mean, err = collect.analyze_one(str(tmp_path / "U=10.0,mu=5.0.dat"))
        assert isinstance(mean, (float, np.floating))
        assert isinstance(err, (float, np.floating))

    def test_err_is_nonnegative(self, tmp_path):
        """誤差は非負"""
        _make_test_dat(str(tmp_path), U=10.0, mu=5.0)
        _, err = collect.analyze_one(str(tmp_path / "U=10.0,mu=5.0.dat"))
        assert err >= 0

    def test_uses_midpoint(self, tmp_path):
        """格子中央(Nx//2)の相関値を返す"""
        Nx = 6
        val = 3.0 + 0j
        samples = [(np.full(Nx, val), np.full(Nx, val))] * 10
        datfile = str(tmp_path / "const.dat")
        _make_binary_dat(datfile, Nx, 10.0, 5.0, 100, samples)
        mean, err = collect.analyze_one(datfile)
        # <a[0]*a*[Nx/2]> = 3.0 * 3.0 = 9.0
        assert mean == pytest.approx(9.0, abs=1e-10)


class TestCollectResults:
    def test_collects_matching_files(self, tmp_path):
        """U=...,mu=...形式のファイルを収集"""
        _make_test_dat(str(tmp_path), U=10.0, mu=0.0)
        _make_test_dat(str(tmp_path), U=10.0, mu=2.0)
        _make_test_dat(str(tmp_path), U=10.0, mu=4.0)
        results = collect.collect_results(str(tmp_path))
        assert len(results) == 3
        assert (10.0, 0.0) in results
        assert (10.0, 2.0) in results
        assert (10.0, 4.0) in results

    def test_ignores_non_matching_files(self, tmp_path):
        """形式の異なるファイルは無視"""
        _make_test_dat(str(tmp_path), U=10.0, mu=0.0)
        # 無関係なファイル
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "params.dat").write_text("test")
        results = collect.collect_results(str(tmp_path))
        assert len(results) == 1

    def test_empty_dir(self, tmp_path):
        """空ディレクトリ → 空dict"""
        results = collect.collect_results(str(tmp_path))
        assert results == {}

    def test_result_values_are_tuples(self, tmp_path):
        """結果は (mean, err) タプル"""
        _make_test_dat(str(tmp_path), U=5.0, mu=1.0)
        results = collect.collect_results(str(tmp_path))
        mean, err = results[(5.0, 1.0)]
        assert isinstance(mean, (float, np.floating))
        assert isinstance(err, (float, np.floating))


class TestPlotSweep:
    def test_creates_figure(self, tmp_path):
        """PNGファイルを作成"""
        sweep_values = [0.0, 2.0, 4.0]
        means = [1.0, 2.0, 1.5]
        errs = [0.1, 0.2, 0.15]
        figname = collect.plot_sweep(
            sweep_values, means, errs,
            "mu", "U", 10.0, 100, str(tmp_path))
        assert os.path.exists(figname)
        assert figname.endswith(".png")

    def test_filename_contains_params(self, tmp_path):
        """ファイル名にパラメータ情報を含む"""
        figname = collect.plot_sweep(
            [0], [1], [0.1],
            "U", "mu", 5.0, 200, str(tmp_path))
        assert "sweep_U" in figname
        assert "mu=5.0" in figname
