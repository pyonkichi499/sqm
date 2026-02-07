"""read_dat_mod のテスト (jackknife, compute_correlation, read_dat)"""
import struct
import numpy as np
import pytest
import read_dat_mod


class TestJackknife:
    def test_constant_array(self):
        """定数配列 → 誤差ゼロ"""
        arr = [5.0] * 10
        mean, err = read_dat_mod.jackknife(arr)
        assert mean == pytest.approx(5.0)
        assert err == pytest.approx(0.0, abs=1e-14)

    def test_known_mean(self):
        """[1, 2, 3, 4, 5] の平均は3"""
        arr = [1.0, 2.0, 3.0, 4.0, 5.0]
        mean, err = read_dat_mod.jackknife(arr)
        assert mean == pytest.approx(3.0)
        assert err > 0

    def test_two_elements(self):
        """2要素"""
        mean, err = read_dat_mod.jackknife([1.0, 3.0])
        assert mean == pytest.approx(2.0)

    def test_complex_input_takes_real(self):
        """複素数入力は実部のみ使用"""
        arr = [1 + 2j, 3 + 4j, 5 + 6j]
        mean, err = read_dat_mod.jackknife(arr)
        assert mean == pytest.approx(3.0)

    def test_numpy_array_input(self):
        """np.array入力"""
        arr = np.array([2.0, 4.0, 6.0])
        mean, err = read_dat_mod.jackknife(arr)
        assert mean == pytest.approx(4.0)

    def test_error_nonzero_for_varying_data(self):
        """変動するデータの誤差は正"""
        rng = np.random.default_rng(42)
        arr = rng.normal(0, 1, 100)
        mean, err = read_dat_mod.jackknife(arr)
        assert err > 0


class TestComputeCorrelation:
    def test_identity_correlation(self):
        """a = a_ast = 定数 → 相関は定数の二乗"""
        Nx = 4
        N = 10
        val = 2.0 + 0j
        a_list = [np.full(Nx, val, dtype=np.complex128) for _ in range(N)]
        a_ast_list = [np.full(Nx, val, dtype=np.complex128) for _ in range(N)]
        corr_mean, corr_err = read_dat_mod.compute_correlation(a_list, a_ast_list, Nx)
        # <a[0]*a*[x]> = 2.0 * 2.0 = 4.0 for all x
        np.testing.assert_allclose(corr_mean, 4.0, atol=1e-12)
        np.testing.assert_allclose(corr_err, 0.0, atol=1e-12)

    def test_output_shape(self):
        """出力配列の長さはNx"""
        Nx = 8
        a_list = [np.ones(Nx, dtype=np.complex128) for _ in range(5)]
        a_ast_list = [np.ones(Nx, dtype=np.complex128) for _ in range(5)]
        corr_mean, corr_err = read_dat_mod.compute_correlation(a_list, a_ast_list, Nx)
        assert len(corr_mean) == Nx
        assert len(corr_err) == Nx

    def test_varying_data_has_nonzero_error(self):
        """ランダムデータでは誤差が正"""
        Nx = 4
        rng = np.random.default_rng(42)
        a_list = [rng.standard_normal(Nx) + 1j * rng.standard_normal(Nx) for _ in range(20)]
        a_ast_list = [rng.standard_normal(Nx) + 1j * rng.standard_normal(Nx) for _ in range(20)]
        corr_mean, corr_err = read_dat_mod.compute_correlation(a_list, a_ast_list, Nx)
        assert all(e > 0 for e in corr_err)


def _make_binary_dat(path, Nx, U, mu, Ntau, samples):
    """テスト用のFortranバイナリ .dat ファイルを作成"""
    with open(path, 'wb') as f:
        # header record: Fortran record marker = byte size of record
        header_size = 4 + 8 + 8 + 4  # Nx(i4) + U(f8) + mu(f8) + Ntau(i4)
        f.write(struct.pack('<i', header_size))
        f.write(struct.pack('<i', Nx))
        f.write(struct.pack('<d', U))
        f.write(struct.pack('<d', mu))
        f.write(struct.pack('<i', Ntau))
        f.write(struct.pack('<i', header_size))

        # body records
        body_size = Nx * 16 + Nx * 16  # a(Nx*c16) + a_ast(Nx*c16)
        for a, a_ast in samples:
            f.write(struct.pack('<i', body_size))
            for c in a:
                f.write(struct.pack('<dd', c.real, c.imag))
            for c in a_ast:
                f.write(struct.pack('<dd', c.real, c.imag))
            f.write(struct.pack('<i', body_size))


class TestReadDat:
    def test_read_header(self, tmp_path):
        """ヘッダーのパラメータが正しく読み込めること"""
        Nx, U, mu, Ntau = 4, 10.0, 3.5, 100
        a = np.array([1 + 0j, 0, 0, 0], dtype=np.complex128)
        datfile = str(tmp_path / "test.dat")
        _make_binary_dat(datfile, Nx, U, mu, Ntau, [(a, a)])

        header, body = read_dat_mod.read_dat(datfile)
        assert header[0]['Nx'] == Nx
        assert header[0]['U'] == pytest.approx(U)
        assert header[0]['mu'] == pytest.approx(mu)
        assert header[0]['Ntau'] == Ntau

    def test_read_body_count(self, tmp_path):
        """サンプル数が正しく読み込めること"""
        Nx = 2
        a = np.array([1 + 0j, 2 + 0j], dtype=np.complex128)
        samples = [(a, a)] * 5
        datfile = str(tmp_path / "test.dat")
        _make_binary_dat(datfile, Nx, 1.0, 0.0, 10, samples)

        header, body = read_dat_mod.read_dat(datfile)
        assert len(body) == 5

    def test_read_body_values(self, tmp_path):
        """ボディのa, a_ast値が正しいこと"""
        Nx = 2
        a = np.array([1.5 + 2.5j, 3.0 - 1.0j], dtype=np.complex128)
        a_ast = np.array([0.5 + 0.5j, -1.0 + 0j], dtype=np.complex128)
        datfile = str(tmp_path / "test.dat")
        _make_binary_dat(datfile, Nx, 1.0, 0.0, 10, [(a, a_ast)])

        _, body = read_dat_mod.read_dat(datfile)
        np.testing.assert_allclose(body[0]['a'], a)
        np.testing.assert_allclose(body[0]['a_ast'], a_ast)

    def test_read_multiple_samples(self, tmp_path):
        """複数サンプルの読み込み"""
        Nx = 3
        rng = np.random.default_rng(123)
        samples = []
        for _ in range(10):
            a = rng.standard_normal(Nx) + 1j * rng.standard_normal(Nx)
            a_ast = rng.standard_normal(Nx) + 1j * rng.standard_normal(Nx)
            samples.append((a, a_ast))
        datfile = str(tmp_path / "test.dat")
        _make_binary_dat(datfile, Nx, 20.0, 5.0, 50, samples)

        header, body = read_dat_mod.read_dat(datfile)
        assert len(body) == 10
        for i, (a_orig, a_ast_orig) in enumerate(samples):
            np.testing.assert_allclose(body[i]['a'], a_orig, atol=1e-14)
            np.testing.assert_allclose(body[i]['a_ast'], a_ast_orig, atol=1e-14)
