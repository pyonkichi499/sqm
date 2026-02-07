"""wparams.write_params のテスト"""
import os
import pytest
import wparams


def test_write_params_creates_file(tmp_path):
    paramsfile = str(tmp_path / "params.dat")
    wparams.write_params(mu=5.0, U=20.0, Nsample=100,
                         filename="out.dat", paramsfile=paramsfile)
    assert os.path.exists(paramsfile)


def test_write_params_namelist_format(tmp_path):
    paramsfile = str(tmp_path / "params.dat")
    wparams.write_params(mu=3.0, U=10.0, Nsample=50,
                         filename="result.dat", paramsfile=paramsfile)
    content = open(paramsfile).read()
    assert "&params" in content
    assert "&sampling_setting" in content
    assert "mu = 3.0" in content
    assert "U = 10.0" in content
    assert 'datfilename = "result.dat"' in content
    assert "Nsample = 50" in content
    # Fortran namelist ends with /
    assert content.count("/") >= 2


def test_write_params_default_values(tmp_path):
    paramsfile = str(tmp_path / "params.dat")
    wparams.write_params(mu=0, U=20, Nsample=200,
                         filename="out.dat", paramsfile=paramsfile)
    content = open(paramsfile).read()
    assert "dtau = 0.3d0" in content
    assert "ds = 0.3d-5" in content
    assert "s_end = 1d0" in content


def test_write_params_custom_values(tmp_path):
    paramsfile = str(tmp_path / "params.dat")
    wparams.write_params(mu=1, U=5, Nsample=100, filename="out.dat",
                         paramsfile=paramsfile,
                         dtau="0.1d0", ds="1d-6", s_end="2d0")
    content = open(paramsfile).read()
    assert "dtau = 0.1d0" in content
    assert "ds = 1d-6" in content
    assert "s_end = 2d0" in content
