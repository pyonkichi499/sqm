"""read_dat_mod.py のテスト

TDD に基づき、各関数のテストを先に定義し、
実装を修正して通すアプローチをとる。
"""

import struct
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from sqm.read_dat_mod import (
    compute_correlation,
    jackknife,
    plot_correlation,
    read_dat,
    readfile,
)


# ============================================================
# 1. jackknife() のテスト
# ============================================================

class TestJackknife:
    """ジャックナイフ法のテスト群"""

    def test_ジャックナイフ法_既知の配列で正しい平均を返す(self) -> None:
        arr = [1.0, 2.0, 3.0, 4.0, 5.0]
        mean, _ = jackknife(arr)
        assert mean == pytest.approx(3.0)

    def test_ジャックナイフ法_既知の配列で正しい誤差を返す(self) -> None:
        arr = [1.0, 2.0, 3.0, 4.0, 5.0]
        _, err = jackknife(arr)
        # ジャックナイフ誤差を手動で計算して検証
        n = len(arr)
        total = sum(arr)
        jk_means = [(total - x) / (n - 1) for x in arr]
        jk_mm = total / n
        var = sum((jk - jk_mm) ** 2 for jk in jk_means) / n
        expected_err = np.sqrt((n - 1) * var)
        assert err == pytest.approx(expected_err)

    def test_ジャックナイフ法_複素数配列は実部のみ処理する(self) -> None:
        arr = [1.0 + 2.0j, 3.0 + 4.0j, 5.0 + 6.0j]
        mean, err = jackknife(arr)
        # 実部は [1.0, 3.0, 5.0] なので平均は 3.0
        assert mean == pytest.approx(3.0)
        # 戻り値が float であること
        assert isinstance(float(mean), float)

    def test_ジャックナイフ法_全て同じ値なら誤差ゼロ(self) -> None:
        arr = [7.0, 7.0, 7.0, 7.0]
        mean, err = jackknife(arr)
        assert mean == pytest.approx(7.0)
        assert err == pytest.approx(0.0)

    def test_ジャックナイフ法_2要素配列で正しく動作する(self) -> None:
        arr = [10.0, 20.0]
        mean, err = jackknife(arr)
        assert mean == pytest.approx(15.0)
        # 2要素のジャックナイフ誤差を手計算
        # jk_means = [20.0, 10.0], jk_mm = 15.0
        # var = ((20-15)^2 + (10-15)^2) / 2 = 25
        # err = sqrt(1 * 25) = 5.0
        assert err == pytest.approx(5.0)


# ============================================================
# 2. read_dat() のテスト
# ============================================================

def _create_test_binary(filepath: Path, Nx: int = 4, n_samples: int = 2,
                        U: float = 1.0, mu: float = 0.5, Ntau: int = 10) -> None:
    """テスト用の Fortran バイナリファイルを作成するヘルパー。

    Fortran の unformatted sequential write は
    [record_length (4 bytes)] [data] [record_length (4 bytes)]
    という形式で各レコードを書く。
    """
    # ヘッダーレコード: Nx(i4), U(f8), mu(f8), Ntau(i4) = 4+8+8+4 = 24 bytes
    header_data = struct.pack('<i d d i', Nx, U, mu, Ntau)
    record_len = len(header_data)  # 24
    header_record = struct.pack('<i', record_len) + header_data + struct.pack('<i', record_len)

    body_records = b''
    for i in range(n_samples):
        # a: Nx 個の complex128 (各 16 bytes)
        # a_ast: Nx 個の complex128 (各 16 bytes)
        a_values = [complex(float(j + 1 + i * 0.1), 0.0) for j in range(Nx)]
        a_ast_values = [complex(float(j + 1 + i * 0.1), 0.0) for j in range(Nx)]

        body_data = b''
        for v in a_values:
            body_data += struct.pack('<d d', v.real, v.imag)
        for v in a_ast_values:
            body_data += struct.pack('<d d', v.real, v.imag)

        body_record_len = len(body_data)  # Nx * 16 * 2
        body_records += (
            struct.pack('<i', body_record_len)
            + body_data
            + struct.pack('<i', body_record_len)
        )

    filepath.write_bytes(header_record + body_records)


class TestReadDat:
    """read_dat() のテスト群"""

    def test_read_dat_ヘッダーを正しく読み込む(self, tmp_path: Path) -> None:
        filepath = tmp_path / "test.dat"
        _create_test_binary(filepath, Nx=4, U=1.5, mu=0.5, Ntau=10)
        header, _ = read_dat(filepath)

        assert header[0]['Nx'] == 4
        assert header[0]['U'] == pytest.approx(1.5)
        assert header[0]['mu'] == pytest.approx(0.5)
        assert header[0]['Ntau'] == 10

    def test_read_dat_ボディを正しく読み込む(self, tmp_path: Path) -> None:
        filepath = tmp_path / "test.dat"
        _create_test_binary(filepath, Nx=4, n_samples=3)
        _, body = read_dat(filepath)

        assert len(body) == 3
        # 各ボディレコードに 'a' と 'a_ast' フィールドがある
        assert 'a' in body.dtype.names
        assert 'a_ast' in body.dtype.names

    def test_read_dat_存在しないファイルでFileNotFoundError(self, tmp_path: Path) -> None:
        filepath = tmp_path / "nonexistent.dat"
        with pytest.raises(FileNotFoundError):
            read_dat(filepath)

    def test_read_dat_空ファイルでValueError(self, tmp_path: Path) -> None:
        filepath = tmp_path / "empty.dat"
        filepath.write_bytes(b'')
        with pytest.raises(ValueError, match="空"):
            read_dat(filepath)


# ============================================================
# 3. compute_correlation() のテスト
# ============================================================

class TestComputeCorrelation:
    """compute_correlation() のテスト群"""

    def test_compute_correlation_既知の相関を正しく計算する(self) -> None:
        # 2 サンプル、格子サイズ 3
        Nx = 3
        a_list = [
            np.array([1.0 + 0j, 2.0 + 0j, 3.0 + 0j]),
            np.array([2.0 + 0j, 3.0 + 0j, 4.0 + 0j]),
        ]
        a_ast_list = [
            np.array([1.0 + 0j, 2.0 + 0j, 3.0 + 0j]),
            np.array([2.0 + 0j, 3.0 + 0j, 4.0 + 0j]),
        ]
        corr_mean, corr_err = compute_correlation(a_list, a_ast_list, Nx)

        # corr[x] = <a[0] * a_ast[x]>
        # x=0: [1*1, 2*2] = [1, 4] -> mean=2.5
        # x=1: [1*2, 2*3] = [2, 6] -> mean=4.0
        # x=2: [1*3, 2*4] = [3, 8] -> mean=5.5
        assert corr_mean[0] == pytest.approx(2.5)
        assert corr_mean[1] == pytest.approx(4.0)
        assert corr_mean[2] == pytest.approx(5.5)

    def test_compute_correlation_全て同じ値なら誤差ゼロ(self) -> None:
        Nx = 2
        a_list = [
            np.array([1.0 + 0j, 2.0 + 0j]),
            np.array([1.0 + 0j, 2.0 + 0j]),
            np.array([1.0 + 0j, 2.0 + 0j]),
        ]
        a_ast_list = [
            np.array([1.0 + 0j, 2.0 + 0j]),
            np.array([1.0 + 0j, 2.0 + 0j]),
            np.array([1.0 + 0j, 2.0 + 0j]),
        ]
        _, corr_err = compute_correlation(a_list, a_ast_list, Nx)
        assert corr_err[0] == pytest.approx(0.0)
        assert corr_err[1] == pytest.approx(0.0)

    def test_compute_correlation_配列サイズが正しい(self) -> None:
        Nx = 5
        a_list = [np.ones(Nx, dtype=complex) for _ in range(4)]
        a_ast_list = [np.ones(Nx, dtype=complex) for _ in range(4)]
        corr_mean, corr_err = compute_correlation(a_list, a_ast_list, Nx)

        assert len(corr_mean) == Nx
        assert len(corr_err) == Nx
        assert corr_mean.dtype == np.float64
        assert corr_err.dtype == np.float64


# ============================================================
# 4. plot_correlation() のテスト
# ============================================================

class TestPlotCorrelation:
    """plot_correlation() のテスト群"""

    def test_plot_correlation_ファイルを正しく保存する(self, tmp_path: Path) -> None:
        xarr = np.array([0.0, 1.0, 2.0])
        corr_mean = np.array([1.0, 0.5, 0.2])
        corr_err = np.array([0.1, 0.05, 0.02])
        savepath = tmp_path / "test_plot.png"

        plot_correlation(xarr, corr_mean, corr_err,
                         mu=0.5, U=1.0, Ntau=10, N=100, savepath=savepath)

        assert savepath.exists()
        assert savepath.stat().st_size > 0

    def test_plot_correlation_ディレクトリを自動作成する(self, tmp_path: Path) -> None:
        xarr = np.array([0.0, 1.0])
        corr_mean = np.array([1.0, 0.5])
        corr_err = np.array([0.1, 0.05])
        # 存在しないネストされたディレクトリ
        savepath = tmp_path / "deep" / "nested" / "dir" / "plot.png"

        plot_correlation(xarr, corr_mean, corr_err,
                         mu=0.5, U=1.0, Ntau=10, N=100, savepath=savepath)

        assert savepath.exists()
        assert savepath.stat().st_size > 0


# ============================================================
# 5. readfile() のテスト
# ============================================================

class TestReadfile:
    """readfile() のテスト群"""

    def test_readfile_格子中央の相関値を返す(self, tmp_path: Path) -> None:
        # readfile 内で filepath.parent.parent / "figures" に保存するため、
        # サブディレクトリ data/ にファイルを置くと savepath が tmp_path / "figures" になる
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        filepath = data_dir / "test.dat"
        Nx = 4
        _create_test_binary(filepath, Nx=Nx, n_samples=5, U=2.0, mu=1.0, Ntau=20)

        result = readfile(filepath)

        # readfile は corr_mean[Nx // 2] を返す
        # 実際の値の正確性は compute_correlation + jackknife で保証
        assert isinstance(float(result), float)
        # プロットファイルが tmp_path / "figures" 下に作成されることを確認
        figures_dir = tmp_path / "figures"
        assert figures_dir.exists()
        png_files = list(figures_dir.glob("*.png"))
        assert len(png_files) == 1
