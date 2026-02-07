from pathlib import Path

import pytest

from sqm.wparams import write_params


def test_write_params_正しいフォーマットでファイルを作成する(tmp_path):
    """Fortran NAMELIST形式のパラメータファイルが正しく生成される"""
    params_file = tmp_path / "params.dat"
    write_params(mu=2.0, U=10.0, Nsample=100, filename="test.dat", paramsfile=str(params_file))
    content = params_file.read_text()
    assert "&params" in content
    assert "mu = 2.0" in content
    assert "U = 10.0" in content
    assert 'datfilename = "test.dat"' in content
    assert "&sampling_setting" in content
    assert "Nsample = 100" in content
    # Each namelist section ends with /
    assert content.count("/") >= 2


def test_write_params_デフォルト引数が正しく動作する(tmp_path):
    """dtau, ds, s_end のデフォルト値が正しい"""
    params_file = tmp_path / "params.dat"
    write_params(mu=1.0, U=5.0, Nsample=50, filename="out.dat", paramsfile=str(params_file))
    content = params_file.read_text()
    assert "dtau = 0.3d0" in content
    assert "ds = 0.3d-5" in content
    assert "s_end = 1d0" in content


def test_write_params_カスタム値が反映される(tmp_path):
    """カスタムパラメータが正しく書き込まれる"""
    params_file = tmp_path / "params.dat"
    write_params(
        mu=1.0, U=5.0, Nsample=50, filename="out.dat",
        paramsfile=str(params_file), dtau="0.1d0", ds="0.1d-5", s_end="2d0"
    )
    content = params_file.read_text()
    assert "dtau = 0.1d0" in content
    assert "ds = 0.1d-5" in content
    assert "s_end = 2d0" in content


def test_write_params_Pathオブジェクトを受け付ける(tmp_path):
    """pathlib.Pathオブジェクトでも動作する"""
    params_file = tmp_path / "params.dat"
    write_params(mu=1.0, U=5.0, Nsample=50, filename="out.dat", paramsfile=params_file)
    assert params_file.exists()


def test_write_params_親ディレクトリを自動作成する(tmp_path):
    """存在しないディレクトリ配下にファイルを作成できる"""
    params_file = tmp_path / "subdir" / "params.dat"
    write_params(mu=1.0, U=5.0, Nsample=50, filename="out.dat", paramsfile=params_file)
    assert params_file.exists()


def test_write_params_Nsampleが整数としてフォーマットされる(tmp_path):
    """Nsampleが小数点なしの整数として書き込まれる"""
    params_file = tmp_path / "params.dat"
    write_params(mu=1.0, U=5.0, Nsample=200, filename="out.dat", paramsfile=str(params_file))
    content = params_file.read_text()
    assert "Nsample = 200" in content
    # Not "Nsample = 200.0"
    assert "Nsample = 200.0" not in content
