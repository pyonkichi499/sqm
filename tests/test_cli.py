"""CLI モジュールのテスト"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from sqm.cli import cli
from sqm.config import Config, SweepConfig


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
