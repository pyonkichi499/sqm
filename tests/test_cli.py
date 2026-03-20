"""CLI モジュールのテスト"""

from __future__ import annotations

import struct
from pathlib import Path

from click.testing import CliRunner

from sqm.cli import cli
from sqm.config import Config, SweepConfig


def _create_test_binary(
    filepath: Path,
    Nx: int = 4,
    n_samples: int = 30,
    U: float = 20.0,
    mu: float = 1.0,
    Ntau: int = 6,
) -> None:
    """テスト用の Fortran バイナリファイルを作成する。"""
    header_data = struct.pack("<i d d i", Nx, U, mu, Ntau)
    record_len = len(header_data)
    header_record = struct.pack("<i", record_len) + header_data + struct.pack("<i", record_len)
    body_records = b""
    for i in range(n_samples):
        a_values = [complex(float(j + 1 + i * 0.1), 0.0) for j in range(Nx)]
        body_data = b""
        for v in a_values:
            body_data += struct.pack("<d d", v.real, v.imag)
        for v in a_values:
            body_data += struct.pack("<d d", v.real, v.imag)
        body_record_len = len(body_data)
        body_records += (
            struct.pack("<i", body_record_len) + body_data + struct.pack("<i", body_record_len)
        )
    filepath.write_bytes(header_record + body_records)


def test_CLI_ヘルプが表示される():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "SQM" in result.output or "sqm" in result.output


def test_CLI_versionが表示される():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_sweep_muスイープのパラメータが正しく解析される():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "20",
            "--mu-step",
            "2",
            "--nsample",
            "10",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "mu" in result.output
    assert "10 points" in result.output or "10" in result.output


def test_sweep_Uスイープのパラメータが正しく解析される():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--mu",
            "10",
            "--u-start",
            "0",
            "--u-end",
            "30",
            "--u-step",
            "5",
            "--nsample",
            "10",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "U" in result.output


def test_sweep_両方固定でエラー():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--mu",
            "10",
            "--nsample",
            "10",
        ],
    )
    assert result.exit_code != 0


def test_sweep_ドライランでシミュレーションは実行されない():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "4",
            "--mu-step",
            "2",
            "--nsample",
            "10",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_config_init_設定ファイルを生成する(tmp_path):
    runner = CliRunner()
    config_file = tmp_path / "config.yaml"
    result = runner.invoke(cli, ["config", "init", "--output", str(config_file)])
    assert result.exit_code == 0
    assert config_file.exists()


def test_config_show_設定を表示する(tmp_path):
    # First create a config
    runner = CliRunner()
    config_file = tmp_path / "config.yaml"
    runner.invoke(cli, ["config", "init", "--output", str(config_file)])
    # Then show it
    result = runner.invoke(cli, ["config", "show", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "Nsample" in result.output


def test_sweep_verboseオプションでデバッグログが出る():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "4",
            "--mu-step",
            "2",
            "--nsample",
            "10",
            "--dry-run",
            "-v",
        ],
    )
    assert result.exit_code == 0


def test_sweep_quietオプションで出力が減る():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "4",
            "--mu-step",
            "2",
            "--nsample",
            "10",
            "--dry-run",
            "-q",
        ],
    )
    assert result.exit_code == 0


def test_sweep_ワーカー数を指定できる():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "4",
            "--mu-step",
            "2",
            "--nsample",
            "10",
            "--workers",
            "2",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "2 workers" in result.output or "workers: 2" in result.output.lower()


def test_sweep_configファイルからパラメータを読み込める(tmp_path):
    """--config オプションでYAML設定ファイルからシミュレーション設定を読み込める"""
    config_file = tmp_path / "config.yaml"
    cfg = Config()
    cfg.to_yaml(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--config",
            str(config_file),
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "4",
            "--mu-step",
            "2",
            "--nsample",
            "10",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "mu" in result.output


def test_sweep_skip_autocorrelationフラグが認識される():
    """--skip-autocorrelation フラグがエラーにならない"""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "4",
            "--mu-step",
            "2",
            "--nsample",
            "10",
            "--dry-run",
            "--skip-autocorrelation",
        ],
    )
    assert result.exit_code == 0


def test_sweep_nsample省略時にconfigのNsampleが使われる(tmp_path):
    """--nsample 未指定でも config ファイルの Nsample が使われる"""
    config_file = tmp_path / "config.yaml"
    cfg = Config()
    cfg.to_yaml(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--config",
            str(config_file),
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "4",
            "--mu-step",
            "2",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Nsample = 200" in result.output


def test_config_init_Configデータクラスベースで生成する(tmp_path):
    """config init が Config dataclass ベースの YAML を生成する"""
    runner = CliRunner()
    config_file = tmp_path / "config.yaml"
    result = runner.invoke(cli, ["config", "init", "--output", str(config_file)])
    assert result.exit_code == 0
    # Load the generated file and verify structure
    cfg = Config.from_yaml(config_file)
    assert cfg.simulation.Nsample == 200
    assert cfg.simulation.dtau == "0.3d0"
    assert cfg.paths.fortran_binary == Path("./a.out").resolve()


def test_config_show_Configデータクラスベースで表示する(tmp_path):
    """config show が Config dataclass 形式で表示する"""
    runner = CliRunner()
    config_file = tmp_path / "config.yaml"
    cfg = Config()
    cfg.to_yaml(config_file)
    result = runner.invoke(cli, ["config", "show", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "simulation" in result.output
    assert "Nsample" in result.output


def test_sweep_muとUの両方をスイープするとエラー():
    """--mu-start/end/step と --u-start/end/step を同時に指定するとエラー (L112)"""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--mu-start",
            "0",
            "--mu-end",
            "10",
            "--mu-step",
            "2",
            "--u-start",
            "0",
            "--u-end",
            "30",
            "--u-step",
            "5",
        ],
    )
    assert result.exit_code != 0
    assert "Cannot sweep both" in result.output


def test_sweep_固定muとmuスイープを同時指定するとエラー():
    """--mu (固定値) と --mu-start/end/step (スイープ) を同時に指定するとエラー (L115)"""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--mu",
            "5",
            "--mu-start",
            "0",
            "--mu-end",
            "10",
            "--mu-step",
            "2",
        ],
    )
    assert result.exit_code != 0
    assert "Cannot specify both --mu" in result.output


def test_sweep_固定UとUスイープを同時指定するとエラー():
    """--u (固定値) と --u-start/end/step (スイープ) を同時に指定するとエラー (L118)"""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--u-start",
            "0",
            "--u-end",
            "30",
            "--u-step",
            "5",
        ],
    )
    assert result.exit_code != 0
    assert "Cannot specify both --u" in result.output


def test_sweep_スイープ範囲未指定でエラー():
    """スイープ範囲を何も指定しないとエラー (L121)"""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
        ],
    )
    assert result.exit_code != 0
    assert "Must specify a sweep range" in result.output


def test_sweep_実行モードでrun_sweepが呼ばれる(monkeypatch):
    """dry-run でない場合に run_sweep が呼ばれてサマリーが表示される (L178-194)"""
    from unittest.mock import MagicMock

    from sqm.runner import PointResult, SweepResult

    mock_result = SweepResult(
        points=[
            PointResult(
                U=20.0,
                mu=2.0,
                correlation_midpoint=0.5,
                correlation_mean=__import__("numpy").array([0.1, 0.2]),
                correlation_err=__import__("numpy").array([0.01, 0.02]),
            ),
            PointResult(
                U=20.0,
                mu=4.0,
                correlation_midpoint=0.6,
                correlation_mean=__import__("numpy").array([0.1, 0.2]),
                correlation_err=__import__("numpy").array([0.01, 0.02]),
            ),
        ],
        failed=[],
        config=Config(),
        walltime_seconds=5.3,
    )

    mock_run_sweep = MagicMock(return_value=mock_result)
    monkeypatch.setattr("sqm.cli.run_sweep", mock_run_sweep)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "4",
            "--mu-step",
            "2",
            "--nsample",
            "10",
        ],
    )
    assert result.exit_code == 0
    assert "完了: 2 成功, 0 失敗" in result.output
    assert "実行時間: 5.3 秒" in result.output
    assert "出力ディレクトリ" in result.output
    assert "グラフ" in result.output
    mock_run_sweep.assert_called_once()


def test_sweep_実行モードで失敗ポイントが表示される(monkeypatch):
    """run_sweep に失敗ポイントがある場合に失敗情報が表示される (L195-198)"""
    from unittest.mock import MagicMock

    from sqm.runner import SweepResult

    mock_result = SweepResult(
        points=[],
        failed=[(20.0, 6.0, "Fortran binary not found")],
        config=Config(),
        walltime_seconds=1.0,
    )

    mock_run_sweep = MagicMock(return_value=mock_result)
    monkeypatch.setattr("sqm.cli.run_sweep", mock_run_sweep)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--u",
            "20",
            "--mu-start",
            "0",
            "--mu-end",
            "10",
            "--mu-step",
            "2",
            "--nsample",
            "10",
        ],
    )
    assert result.exit_code == 0
    assert "0 成功, 1 失敗" in result.output
    assert "失敗ポイント:" in result.output
    assert "U=20.0, mu=6.0: Fortran binary not found" in result.output


def test_sweep_Uスイープ実行モードで正しいパラメータが渡される(monkeypatch):
    """U スイープ実行時に固定 mu と sweep U のサマリーが表示される"""
    from unittest.mock import MagicMock

    from sqm.runner import SweepResult

    mock_result = SweepResult(
        points=[],
        failed=[],
        config=Config(),
        walltime_seconds=0.5,
    )

    mock_run_sweep = MagicMock(return_value=mock_result)
    monkeypatch.setattr("sqm.cli.run_sweep", mock_run_sweep)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sweep",
            "--mu",
            "10",
            "--u-start",
            "0",
            "--u-end",
            "30",
            "--u-step",
            "10",
            "--nsample",
            "5",
        ],
    )
    assert result.exit_code == 0
    assert "Sweep U" in result.output
    assert "fixed mu=10" in result.output


# ============================================================
# analyze コマンドのテスト
# ============================================================


def test_analyze_ヘルプが表示される():
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.output


def test_analyze_既存datファイルの解析(tmp_path: Path):
    """既存の .dat ファイルを解析できる"""
    dat_file = tmp_path / "test.dat"
    _create_test_binary(dat_file, Nx=4, n_samples=30, U=20.0, mu=1.0)

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--input", str(dat_file)])
    assert result.exit_code == 0
    assert "サンプル数" in result.output
    assert "相関関数" in result.output


def test_analyze_存在しないファイルでエラー():
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--input", "/nonexistent/file.dat"])
    assert result.exit_code != 0


def test_analyze_autocorrelation結果を表示(tmp_path: Path):
    """--skip-autocorrelation なしで自己相関情報も表示"""
    dat_file = tmp_path / "test.dat"
    _create_test_binary(dat_file, Nx=4, n_samples=30, U=20.0, mu=1.0)

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--input", str(dat_file)])
    assert result.exit_code == 0
    assert "tau_int" in result.output or "有効サンプル数" in result.output


def test_analyze_skip_autocorrelationフラグ(tmp_path: Path):
    """--skip-autocorrelation で自己相関解析をスキップ"""
    dat_file = tmp_path / "test.dat"
    _create_test_binary(dat_file, Nx=4, n_samples=30, U=20.0, mu=1.0)

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--input", str(dat_file), "--skip-autocorrelation"])
    assert result.exit_code == 0
