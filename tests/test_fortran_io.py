"""fortran_io.py のテスト

Fortran バイナリ I/O (read_dat) およびパラメータファイル生成 (write_params) の
テストを TDD に基づいて定義する。
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from sqm.fortran_io import read_dat, write_params

# ============================================================
# テスト用ヘルパー
# ============================================================


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
# 1. read_dat() のテスト
# ============================================================


class TestReadDat:
    """read_dat() のテスト群"""

    def test_read_dat_ヘッダーを正しく読み込む(self, tmp_path: Path) -> None:
        filepath = tmp_path / "test.dat"
        _create_test_binary(filepath, Nx=4, U=1.5, mu=0.5, Ntau=10)
        header, _ = read_dat(filepath)

        assert header[0]["Nx"] == 4
        assert header[0]["U"] == pytest.approx(1.5)
        assert header[0]["mu"] == pytest.approx(0.5)
        assert header[0]["Ntau"] == 10

    def test_read_dat_ボディを正しく読み込む(self, tmp_path: Path) -> None:
        filepath = tmp_path / "test.dat"
        _create_test_binary(filepath, Nx=4, n_samples=3)
        _, body = read_dat(filepath)

        assert len(body) == 3
        # 各ボディレコードに 'a' と 'a_ast' フィールドがある
        assert "a" in body.dtype.names
        assert "a_ast" in body.dtype.names

    def test_read_dat_存在しないファイルでFileNotFoundError(self, tmp_path: Path) -> None:
        filepath = tmp_path / "nonexistent.dat"
        with pytest.raises(FileNotFoundError):
            read_dat(filepath)

    def test_read_dat_空ファイルでValueError(self, tmp_path: Path) -> None:
        filepath = tmp_path / "empty.dat"
        filepath.write_bytes(b"")
        with pytest.raises(ValueError, match="空"):
            read_dat(filepath)


# ============================================================
# 2. write_params() のテスト
# ============================================================


class TestWriteParams:
    """write_params() のテスト群"""

    def test_write_params_正しいフォーマットでファイルを作成する(self, tmp_path: Path) -> None:
        """Fortran NAMELIST形式のパラメータファイルが正しく生成される"""
        params_file = tmp_path / "params.dat"
        write_params(
            mu=2.0,
            U=10.0,
            Nsample=100,
            filename="test.dat",
            paramsfile=str(params_file),
        )
        content = params_file.read_text()
        assert "&params" in content
        assert "mu = 2.0" in content
        assert "U = 10.0" in content
        assert 'datfilename = "test.dat"' in content
        assert "&sampling_setting" in content
        assert "Nsample = 100" in content
        # Each namelist section ends with /
        assert content.count("/") >= 2

    def test_write_params_デフォルト引数が正しく動作する(self, tmp_path: Path) -> None:
        """dtau, ds, s_end のデフォルト値が正しい"""
        params_file = tmp_path / "params.dat"
        write_params(
            mu=1.0,
            U=5.0,
            Nsample=50,
            filename="out.dat",
            paramsfile=str(params_file),
        )
        content = params_file.read_text()
        assert "dtau = 0.3d0" in content
        assert "ds = 0.3d-5" in content
        assert "s_end = 1d0" in content

    def test_write_params_カスタム値が反映される(self, tmp_path: Path) -> None:
        """カスタムパラメータが正しく書き込まれる"""
        params_file = tmp_path / "params.dat"
        write_params(
            mu=1.0,
            U=5.0,
            Nsample=50,
            filename="out.dat",
            paramsfile=str(params_file),
            dtau="0.1d0",
            ds="0.1d-5",
            s_end="2d0",
        )
        content = params_file.read_text()
        assert "dtau = 0.1d0" in content
        assert "ds = 0.1d-5" in content
        assert "s_end = 2d0" in content

    def test_write_params_Pathオブジェクトを受け付ける(self, tmp_path: Path) -> None:
        """pathlib.Pathオブジェクトでも動作する"""
        params_file = tmp_path / "params.dat"
        write_params(
            mu=1.0,
            U=5.0,
            Nsample=50,
            filename="out.dat",
            paramsfile=params_file,
        )
        assert params_file.exists()

    def test_write_params_親ディレクトリを自動作成する(self, tmp_path: Path) -> None:
        """存在しないディレクトリ配下にファイルを作成できる"""
        params_file = tmp_path / "subdir" / "params.dat"
        write_params(
            mu=1.0,
            U=5.0,
            Nsample=50,
            filename="out.dat",
            paramsfile=params_file,
        )
        assert params_file.exists()

    def test_write_params_Nsampleが整数としてフォーマットされる(self, tmp_path: Path) -> None:
        """Nsampleが小数点なしの整数として書き込まれる"""
        params_file = tmp_path / "params.dat"
        write_params(
            mu=1.0,
            U=5.0,
            Nsample=200,
            filename="out.dat",
            paramsfile=str(params_file),
        )
        content = params_file.read_text()
        assert "Nsample = 200" in content
        # Not "Nsample = 200.0"
        assert "Nsample = 200.0" not in content
