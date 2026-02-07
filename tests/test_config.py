"""設定管理モジュールのテスト

TDD Round 1: SimulationConfig dataclass
TDD Round 2: PathConfig
TDD Round 3: SweepConfig
TDD Round 4: SeedConfig
TDD Round 5: Config (統合 + YAML/JSON シリアライゼーション)
"""
from pathlib import Path

import pytest

from sqm.config import Config, PathConfig, SeedConfig, SimulationConfig, SweepConfig

# =============================================================================
# Round 1: SimulationConfig
# =============================================================================


def test_SimulationConfig_デフォルト値が正しい():
    """デフォルトのシミュレーションパラメータが正しい"""
    cfg = SimulationConfig()
    assert cfg.dtau == "0.3d0"
    assert cfg.ds == "0.3d-5"
    assert cfg.s_end == "1d0"
    assert cfg.Nsample == 200


def test_SimulationConfig_カスタム値を設定できる():
    """カスタム値でシミュレーションパラメータを上書きできる"""
    cfg = SimulationConfig(dtau="0.1d0", Nsample=500)
    assert cfg.dtau == "0.1d0"
    assert cfg.Nsample == 500


# =============================================================================
# Round 2: PathConfig
# =============================================================================


def test_PathConfig_デフォルトパスが正しい():
    """デフォルトのパス設定が正しい"""
    cfg = PathConfig()
    assert cfg.output_dir == Path(".")
    assert cfg.figures_dir == Path("./figures")
    assert cfg.fortran_binary == Path("./a.out")


def test_PathConfig_文字列からPathに変換される():
    """文字列で指定してもPath型に変換される"""
    cfg = PathConfig(output_dir="./output")
    assert isinstance(cfg.output_dir, Path)
    assert cfg.output_dir == Path("./output")


# =============================================================================
# Round 3: SweepConfig
# =============================================================================


def test_SweepConfig_muスイープを設定できる():
    """Uを固定してmuをスイープできる"""
    cfg = SweepConfig(U=20.0, mu_start=0.0, mu_end=20.0, mu_step=2.0)
    assert cfg.sweep_param == "mu"
    values = cfg.sweep_values()
    assert len(values) == 10
    assert values[0] == 0.0


def test_SweepConfig_Uスイープを設定できる():
    """muを固定してUをスイープできる"""
    cfg = SweepConfig(mu=10.0, U_start=0.0, U_end=30.0, U_step=5.0)
    assert cfg.sweep_param == "U"
    values = cfg.sweep_values()
    assert len(values) == 6
    assert values[0] == 0.0
    assert values[-1] == 25.0


def test_SweepConfig_両方固定でValueError():
    """UとmuをどちらもスカラーにするとValueError"""
    with pytest.raises(ValueError):
        SweepConfig(U=20.0, mu=10.0)


def test_SweepConfig_両方スイープでValueError():
    """UとmuをどちらもスイープするとValueError"""
    with pytest.raises(ValueError):
        SweepConfig(
            U_start=0, U_end=10, U_step=1,
            mu_start=0, mu_end=10, mu_step=1,
        )


# =============================================================================
# Round 4: SeedConfig
# =============================================================================


def test_SeedConfig_デフォルトはシステムエントロピー():
    """デフォルトモードはsystem（OS乱数源を使用）"""
    cfg = SeedConfig()
    assert cfg.mode == "system"
    assert cfg.base_seed is None


def test_SeedConfig_固定シードを設定できる():
    """固定シードモードで再現可能な乱数を使用できる"""
    cfg = SeedConfig(mode="fixed", base_seed=42)
    assert cfg.mode == "fixed"
    assert cfg.base_seed == 42


def test_SeedConfig_ハイブリッドモードで異なるシード生成():
    """ハイブリッドモードでプロセスごとに異なるシードを生成する"""
    cfg = SeedConfig(mode="hybrid", base_seed=1000)
    seed1 = cfg.get_seed(process_id=0)
    seed2 = cfg.get_seed(process_id=1)
    assert seed1 != seed2


def test_SeedConfig_固定モードで同じシードが返る():
    """固定シードモードではプロセスIDに関係なく同じシードが返る"""
    cfg = SeedConfig(mode="fixed", base_seed=42)
    seed1 = cfg.get_seed(process_id=0)
    seed2 = cfg.get_seed(process_id=1)
    assert seed1 == 42
    assert seed2 == 42


def test_SeedConfig_systemモードでget_seedはNone():
    """systemモードではget_seedがNoneを返す"""
    cfg = SeedConfig()
    assert cfg.get_seed(process_id=0) is None


# =============================================================================
# Round 5: Config (統合 + YAML/JSON)
# =============================================================================


def test_Config_全設定を統合できる():
    """Configオブジェクトが全サブ設定を含む"""
    cfg = Config()
    assert isinstance(cfg.simulation, SimulationConfig)
    assert isinstance(cfg.paths, PathConfig)


def test_Config_YAMLファイルから読み込める(tmp_path: Path):
    """YAML設定ファイルを読み込んでConfigを構築できる"""
    yaml_content = """\
simulation:
  dtau: "0.1d0"
  Nsample: 500
paths:
  output_dir: "./output"
  figures_dir: "./figs"
sweep:
  U: 20.0
  mu_start: 0.0
  mu_end: 20.0
  mu_step: 2.0
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    cfg = Config.from_yaml(config_file)
    assert cfg.simulation.dtau == "0.1d0"
    assert cfg.simulation.Nsample == 500
    assert cfg.paths.output_dir == Path("./output")
    assert cfg.sweep is not None
    assert cfg.sweep.sweep_param == "mu"


def test_Config_YAMLファイルに書き出せる(tmp_path: Path):
    """ConfigをYAMLファイルに書き出して再読み込みできる"""
    cfg = Config()
    output_file = tmp_path / "config.yaml"
    cfg.to_yaml(output_file)
    assert output_file.exists()

    loaded = Config.from_yaml(output_file)
    assert loaded.simulation.Nsample == cfg.simulation.Nsample
    assert loaded.simulation.dtau == cfg.simulation.dtau
    assert loaded.paths.output_dir == cfg.paths.output_dir


def test_Config_JSONファイルから読み込める(tmp_path: Path):
    """JSON設定ファイルを読み込んでConfigを構築できる"""
    json_content = '{"simulation": {"Nsample": 300}}'
    config_file = tmp_path / "config.json"
    config_file.write_text(json_content)

    cfg = Config.from_json(config_file)
    assert cfg.simulation.Nsample == 300


def test_Config_JSONファイルに書き出せる(tmp_path: Path):
    """ConfigをJSONファイルに書き出して再読み込みできる"""
    cfg = Config()
    output_file = tmp_path / "config.json"
    cfg.to_json(output_file)
    assert output_file.exists()

    loaded = Config.from_json(output_file)
    assert loaded.simulation.Nsample == cfg.simulation.Nsample
    assert loaded.simulation.dtau == cfg.simulation.dtau


def test_Config_存在しないYAMLファイルでFileNotFoundError():
    """存在しないファイルを読み込もうとするとFileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        Config.from_yaml(Path("/nonexistent/config.yaml"))


def test_Config_存在しないJSONファイルでFileNotFoundError():
    """存在しないファイルを読み込もうとするとFileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        Config.from_json(Path("/nonexistent/config.json"))
