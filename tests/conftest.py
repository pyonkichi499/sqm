from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def fixture_dir() -> Path:
    """テストフィクスチャディレクトリのパス"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """一時出力ディレクトリ（figures/ と output/ を含む）"""
    (tmp_path / "figures").mkdir()
    (tmp_path / "output").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def fix_random_seed() -> None:
    """全テストで乱数シードを固定"""
    np.random.seed(42)
