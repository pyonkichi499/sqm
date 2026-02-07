"""simulate.py のテスト"""
import os
import sys
from unittest.mock import patch, MagicMock
import pytest

import simulate
import wparams


class TestRunOne:
    def test_creates_outdir(self, tmp_path):
        """outdir が作成されること"""
        outdir = str(tmp_path / "newdir")
        with patch("simulate.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            simulate.run_one(10, 5, 100, outdir)
        assert os.path.isdir(outdir)

    def test_calls_a_out(self, tmp_path):
        """./a.out がparamsfileを引数として呼ばれること"""
        with patch("simulate.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            simulate.run_one(10, 5, 100, str(tmp_path))
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "./a.out"
        assert "params_U=10_mu=5.dat" in args[1]

    def test_returns_datfilename(self, tmp_path):
        """戻り値が .dat ファイルパス"""
        with patch("simulate.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = simulate.run_one(20, 3, 200, str(tmp_path))
        assert result.endswith("U=20,mu=3.dat")

    def test_removes_paramsfile(self, tmp_path):
        """実行後にparamsfileが削除されること"""
        with patch("simulate.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            simulate.run_one(10, 5, 100, str(tmp_path))
        # paramsfile should be removed
        params_files = [f for f in os.listdir(str(tmp_path)) if f.startswith("params_")]
        assert len(params_files) == 0

    def test_writes_params_file(self, tmp_path):
        """wparams.write_paramsが呼ばれること"""
        def create_paramsfile(*args, **kwargs):
            # paramsfile kwarg で指定されたファイルを作成
            pf = kwargs.get("paramsfile", args[4] if len(args) > 4 else "params.dat")
            open(pf, "w").close()

        with patch("simulate.run") as mock_run, \
             patch("simulate.wparams.write_params", side_effect=create_paramsfile) as mock_wp:
            mock_run.return_value = MagicMock(returncode=0)
            simulate.run_one(15, 7, 300, str(tmp_path))
        mock_wp.assert_called_once()
        call_kwargs = mock_wp.call_args
        assert call_kwargs[0][0] == 7    # mu
        assert call_kwargs[0][1] == 15   # U
        assert call_kwargs[0][2] == 300  # Nsample

    def test_passes_extra_kwargs(self, tmp_path):
        """追加キーワード引数がwparamsに渡ること"""
        def create_paramsfile(*args, **kwargs):
            pf = kwargs.get("paramsfile", args[4] if len(args) > 4 else "params.dat")
            open(pf, "w").close()

        with patch("simulate.run") as mock_run, \
             patch("simulate.wparams.write_params", side_effect=create_paramsfile) as mock_wp:
            mock_run.return_value = MagicMock(returncode=0)
            simulate.run_one(10, 5, 100, str(tmp_path), dtau="0.1d0")
        assert mock_wp.call_args[1].get("dtau") == "0.1d0"


class TestMainArgParsing:
    def test_default_values(self):
        """デフォルト引数値"""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("SQM_") and k != "CLOUD_RUN_TASK_INDEX"}
        with patch.dict(os.environ, env, clear=True), \
             patch("simulate.run_one") as mock_run_one, \
             patch("sys.argv", ["simulate.py"]):
            mock_run_one.return_value = "output/test.dat"
            simulate.main()
        args = mock_run_one.call_args
        assert args[0][0] == 20    # U default
        assert args[0][1] == 0     # mu default
        assert args[0][2] == 200   # Nsample default

    def test_cli_args(self):
        """CLI引数が反映されること"""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("SQM_") and k != "CLOUD_RUN_TASK_INDEX"}
        with patch.dict(os.environ, env, clear=True), \
             patch("simulate.run_one") as mock_run_one, \
             patch("sys.argv", ["simulate.py", "--U", "15", "--mu", "3", "--Nsample", "500"]):
            mock_run_one.return_value = "output/test.dat"
            simulate.main()
        args = mock_run_one.call_args
        assert args[0][0] == 15
        assert args[0][1] == 3
        assert args[0][2] == 500

    def test_env_vars(self):
        """環境変数からの設定"""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("SQM_") and k != "CLOUD_RUN_TASK_INDEX"}
        env.update({"SQM_U": "30", "SQM_MU": "7", "SQM_NSAMPLE": "1000"})
        with patch.dict(os.environ, env, clear=True), \
             patch("simulate.run_one") as mock_run_one, \
             patch("sys.argv", ["simulate.py"]):
            mock_run_one.return_value = "output/test.dat"
            simulate.main()
        args = mock_run_one.call_args
        assert args[0][0] == 30
        assert args[0][1] == 7
        assert args[0][2] == 1000


class TestCloudRunTaskIndex:
    def test_mu_sweep(self):
        """CLOUD_RUN_TASK_INDEXでmuスイープ"""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("SQM_") and k != "CLOUD_RUN_TASK_INDEX"}
        env.update({
            "CLOUD_RUN_TASK_INDEX": "3",
            "SQM_SWEEP": "mu",
            "SQM_SWEEP_START": "0",
            "SQM_SWEEP_STEP": "2",
        })
        with patch.dict(os.environ, env, clear=True), \
             patch("simulate.run_one") as mock_run_one, \
             patch("sys.argv", ["simulate.py"]):
            mock_run_one.return_value = "output/test.dat"
            simulate.main()
        # mu = 0 + 3 * 2 = 6
        assert mock_run_one.call_args[0][1] == 6.0

    def test_u_sweep(self):
        """CLOUD_RUN_TASK_INDEXでUスイープ"""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("SQM_") and k != "CLOUD_RUN_TASK_INDEX"}
        env.update({
            "CLOUD_RUN_TASK_INDEX": "2",
            "SQM_SWEEP": "U",
            "SQM_SWEEP_START": "5",
            "SQM_SWEEP_STEP": "5",
        })
        with patch.dict(os.environ, env, clear=True), \
             patch("simulate.run_one") as mock_run_one, \
             patch("sys.argv", ["simulate.py"]):
            mock_run_one.return_value = "output/test.dat"
            simulate.main()
        # U = 5 + 2 * 5 = 15
        assert mock_run_one.call_args[0][0] == 15.0

    def test_default_sweep_is_mu(self):
        """SQM_SWEEP未設定時はmuスイープ"""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("SQM_") and k != "CLOUD_RUN_TASK_INDEX"}
        env.update({"CLOUD_RUN_TASK_INDEX": "1"})
        with patch.dict(os.environ, env, clear=True), \
             patch("simulate.run_one") as mock_run_one, \
             patch("sys.argv", ["simulate.py"]):
            mock_run_one.return_value = "output/test.dat"
            simulate.main()
        # default: mu = 0 + 1 * 2 = 2
        assert mock_run_one.call_args[0][1] == 2.0
