"""ExperimentLog モジュールのテスト"""

import json
import time

from sqm.experiment_log import ExperimentLog


def test_ExperimentLog_タイムスタンプ付きで作成される():
    log = ExperimentLog()
    assert log.timestamp is not None
    assert isinstance(log.timestamp, str)


def test_ExperimentLog_パラメータを記録できる():
    log = ExperimentLog()
    log.set_parameters(U=20.0, mu=10.0, Nsample=200, dtau="0.3d0")
    assert log.parameters["U"] == 20.0
    assert log.parameters["Nsample"] == 200


def test_ExperimentLog_git情報を取得できる():
    log = ExperimentLog()
    log.capture_git_info()
    # In a git repo, hash should be set
    assert log.metadata.get("git_hash") is not None


def test_ExperimentLog_git情報がない場合もエラーにならない(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # not a git repo
    log = ExperimentLog()
    log.capture_git_info()
    assert log.metadata.get("git_hash") is None or log.metadata.get("git_hash") == "unknown"


def test_ExperimentLog_環境情報を取得できる():
    log = ExperimentLog()
    log.capture_environment()
    assert "hostname" in log.metadata
    assert "python_version" in log.metadata
    assert "numpy_version" in log.metadata


def test_ExperimentLog_結果を記録できる():
    log = ExperimentLog()
    log.add_result("U=20_mu=10", correlation=0.47, n_samples=185, n_failed=15)
    assert "U=20_mu=10" in log.results
    assert log.results["U=20_mu=10"]["correlation"] == 0.47
    assert log.results["U=20_mu=10"]["n_failed"] == 15


def test_ExperimentLog_失敗率が高い場合に警告():
    log = ExperimentLog()
    log.add_result("U=20_mu=10", correlation=0.47, n_samples=50, n_failed=100)
    warnings = log.get_warnings()
    assert any("failure" in w.lower() or "失敗" in w for w in warnings)


def test_ExperimentLog_JSONファイルに保存できる(tmp_path):
    log = ExperimentLog()
    log.set_parameters(U=20.0, mu=10.0)
    log.add_result("test", correlation=0.5, n_samples=100, n_failed=0)

    output_file = tmp_path / "experiment.json"
    log.save_json(output_file)
    assert output_file.exists()

    with open(output_file) as f:
        data = json.load(f)
    assert data["parameters"]["U"] == 20.0
    assert "timestamp" in data


def test_ExperimentLog_JSONファイルから読み込める(tmp_path):
    log = ExperimentLog()
    log.set_parameters(U=20.0, mu=10.0)
    output_file = tmp_path / "experiment.json"
    log.save_json(output_file)

    loaded = ExperimentLog.load_json(output_file)
    assert loaded.parameters["U"] == 20.0


def test_ExperimentLog_サマリーレポートを生成できる():
    log = ExperimentLog()
    log.set_parameters(U=20.0, mu=10.0, Nsample=200)
    log.capture_environment()
    log.add_result("sweep_1", correlation=0.47, n_samples=185, n_failed=15)
    log.add_result("sweep_2", correlation=0.52, n_samples=195, n_failed=5)

    report = log.summary()
    assert isinstance(report, str)
    assert "U" in report
    assert "sweep" in report.lower() or "result" in report.lower()


def test_ExperimentLog_実行時間を記録できる():
    log = ExperimentLog()
    log.start_timer()
    time.sleep(0.1)
    log.stop_timer()
    assert log.walltime_seconds > 0.05
    assert log.walltime_seconds < 5.0
