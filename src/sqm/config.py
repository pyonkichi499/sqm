"""設定管理モジュール

シミュレーションパラメータを一元管理するための dataclass 群と、
YAML / JSON によるシリアライゼーションを提供する。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

__all__ = [
    "SimulationConfig",
    "PathConfig",
    "SweepConfig",
    "SeedConfig",
    "Config",
]

# =============================================================================
# Round 1: SimulationConfig
# =============================================================================


# Fortran 倍精度リテラルのパターン (例: "0.3d0", "1d-5", "0.3d+2")
_FORTRAN_DOUBLE_RE = re.compile(r"^-?\d+\.?\d*[dD][+-]?\d+$")


@dataclass
class SimulationConfig:
    """Fortran シミュレーションの基本パラメータ"""

    dtau: str = "0.3d0"
    ds: str = "0.3d-5"
    s_end: str = "1d0"
    Nsample: int = 200

    def __post_init__(self) -> None:
        if self.Nsample < 1:
            raise ValueError(f"Nsample は1以上が必要です: {self.Nsample}")
        for name, value in [("dtau", self.dtau), ("ds", self.ds), ("s_end", self.s_end)]:
            if not _FORTRAN_DOUBLE_RE.match(value):
                raise ValueError(
                    f"{name} は Fortran 倍精度リテラル形式が必要です "
                    f'(例: "0.3d0"): "{value}"'
                )


# =============================================================================
# Round 2: PathConfig
# =============================================================================


@dataclass
class PathConfig:
    """ファイルパス設定"""

    output_dir: Path = field(default_factory=lambda: Path("./output"))
    figures_dir: Path = field(default_factory=lambda: Path("./output/figures"))
    fortran_binary: Path = field(default_factory=lambda: Path("./a.out"))

    def __post_init__(self) -> None:
        # 文字列が渡された場合に Path へ変換し、絶対パスに解決する
        self.output_dir = Path(self.output_dir).resolve()
        self.figures_dir = Path(self.figures_dir).resolve()
        self.fortran_binary = Path(self.fortran_binary).resolve()


# =============================================================================
# Round 3: SweepConfig
# =============================================================================


@dataclass
class SweepConfig:
    """パラメータスイープ設定

    U を固定して mu をスイープするか、mu を固定して U をスイープする。
    両方固定 / 両方スイープは ValueError を送出する。
    """

    # 固定値（スイープしない側）
    U: float | None = None
    mu: float | None = None

    # mu スイープ範囲
    mu_start: float | None = None
    mu_end: float | None = None
    mu_step: float | None = None

    # U スイープ範囲
    U_start: float | None = None
    U_end: float | None = None
    U_step: float | None = None

    def __post_init__(self) -> None:
        has_mu_sweep = all(v is not None for v in [self.mu_start, self.mu_end, self.mu_step])
        has_U_sweep = all(v is not None for v in [self.U_start, self.U_end, self.U_step])

        if has_mu_sweep and has_U_sweep:
            raise ValueError("U と mu を同時にスイープすることはできません")

        if self.U is not None and self.mu is not None and not has_mu_sweep and not has_U_sweep:
            raise ValueError(
                "U と mu の両方を固定することはできません。どちらかをスイープしてください"
            )

    @property
    def sweep_param(self) -> str:
        """スイープ対象のパラメータ名を返す"""
        has_mu_sweep = all(v is not None for v in [self.mu_start, self.mu_end, self.mu_step])
        if has_mu_sweep:
            return "mu"
        return "U"

    @staticmethod
    def _generate_range(start: float, end: float, step: float, name: str) -> list[float]:
        """start から end 未満まで step 刻みで等差数列を生成する。"""
        if step <= 0:
            raise ValueError(f"{name}_step は正の値が必要です: {step}")
        values: list[float] = []
        current = start
        while current < end:
            values.append(current)
            current = round(current + step, 10)
        return values

    def sweep_values(self) -> list[float]:
        """スイープ値のリストを返す

        Raises
        ------
        ValueError
            スイープパラメータが未設定、またはステップが 0 以下の場合
        """
        if self.sweep_param == "mu":
            if self.mu_start is None or self.mu_end is None or self.mu_step is None:
                raise ValueError("mu スイープのパラメータが不足しています")
            return self._generate_range(self.mu_start, self.mu_end, self.mu_step, "mu")
        else:
            if self.U_start is None or self.U_end is None or self.U_step is None:
                raise ValueError("U スイープのパラメータが不足しています")
            return self._generate_range(self.U_start, self.U_end, self.U_step, "U")

    def get_sweep_info(self) -> dict[str, Any]:
        """スイープ情報をまとめて返す。

        Returns
        -------
        dict with keys: sweep_name, fixed_name, fixed_value, sweep_values
        """
        sweep_name = self.sweep_param
        values = self.sweep_values()
        if sweep_name == "mu":
            fixed_name = "U"
            fixed_value = self.U if self.U is not None else 0.0
        else:
            fixed_name = "mu"
            fixed_value = self.mu if self.mu is not None else 0.0
        return {
            "sweep_name": sweep_name,
            "fixed_name": fixed_name,
            "fixed_value": fixed_value,
            "sweep_values": values,
        }


# =============================================================================
# Round 4: SeedConfig
# =============================================================================


@dataclass
class SeedConfig:
    """乱数シード設定

    mode:
        "system"  - OS のエントロピー源を使用（デフォルト）
        "fixed"   - base_seed をそのまま使用（再現性確保）
        "hybrid"  - base_seed + process_id でプロセスごとに異なるシード
    """

    mode: str = "system"
    base_seed: int | None = None

    def __post_init__(self) -> None:
        valid_modes = {"system", "fixed", "hybrid"}
        if self.mode not in valid_modes:
            raise ValueError(f"未知のモード: {self.mode} (有効: {valid_modes})")
        if self.mode in ("fixed", "hybrid") and self.base_seed is None:
            raise ValueError(f"{self.mode} モードでは base_seed が必要です")

    def get_seed(self, process_id: int = 0) -> int | None:
        """プロセスIDに応じたシードを返す

        Args:
            process_id: 並列プロセスの識別子

        Returns:
            シード値。system モードでは None を返す。
        """
        if self.mode == "system":
            return None
        if self.mode == "fixed":
            return self.base_seed
        if self.mode == "hybrid":
            if self.base_seed is None:
                raise ValueError("hybrid モードでは base_seed が必要です")
            return self.base_seed + process_id
        raise ValueError(f"未知のモード: {self.mode}")


# =============================================================================
# Round 5: Config (統合)
# =============================================================================


@dataclass
class Config:
    """全設定を統合するトップレベル設定クラス"""

    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    sweep: SweepConfig | None = None
    seed: SeedConfig = field(default_factory=SeedConfig)

    # -------------------------------------------------------------------------
    # YAML
    # -------------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Path) -> Config:
        """YAML ファイルから Config を構築する"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
        with open(path, encoding="utf-8") as f:
            try:
                data: dict[str, Any] = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"YAML パースエラー ({path}): {e}") from e
        return cls._from_dict(data)

    def to_yaml(self, path: Path) -> None:
        """Config を YAML ファイルに書き出す"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._to_dict(), f, default_flow_style=False, allow_unicode=True)

    # -------------------------------------------------------------------------
    # JSON
    # -------------------------------------------------------------------------

    @classmethod
    def from_json(cls, path: Path) -> Config:
        """JSON ファイルから Config を構築する"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
        with open(path, encoding="utf-8") as f:
            try:
                data: dict[str, Any] = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON パースエラー ({path}): {e}") from e
        return cls._from_dict(data)

    def to_json(self, path: Path) -> None:
        """Config を JSON ファイルに書き出す"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._to_dict(), f, indent=2, ensure_ascii=False)

    # -------------------------------------------------------------------------
    # dict 変換ヘルパー
    # -------------------------------------------------------------------------

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Config:
        """辞書から Config を構築する"""
        sim_data = data.get("simulation", {})
        paths_data = data.get("paths", {})
        sweep_data = data.get("sweep")
        seed_data = data.get("seed", {})

        simulation = SimulationConfig(**sim_data) if sim_data else SimulationConfig()
        paths = PathConfig(**paths_data) if paths_data else PathConfig()
        sweep = SweepConfig(**sweep_data) if sweep_data else None
        seed = SeedConfig(**seed_data) if seed_data else SeedConfig()

        return cls(
            simulation=simulation,
            paths=paths,
            sweep=sweep,
            seed=seed,
        )

    def _to_dict(self) -> dict[str, Any]:
        """Config を辞書に変換する"""
        result: dict[str, Any] = {
            "simulation": {
                "dtau": self.simulation.dtau,
                "ds": self.simulation.ds,
                "s_end": self.simulation.s_end,
                "Nsample": self.simulation.Nsample,
            },
            "paths": {
                "output_dir": str(self.paths.output_dir),
                "figures_dir": str(self.paths.figures_dir),
                "fortran_binary": str(self.paths.fortran_binary),
            },
            "seed": {
                "mode": self.seed.mode,
                "base_seed": self.seed.base_seed,
            },
        }
        if self.sweep is not None:
            sweep_dict: dict[str, Any] = {}
            if self.sweep.U is not None:
                sweep_dict["U"] = self.sweep.U
            if self.sweep.mu is not None:
                sweep_dict["mu"] = self.sweep.mu
            if self.sweep.mu_start is not None:
                sweep_dict["mu_start"] = self.sweep.mu_start
            if self.sweep.mu_end is not None:
                sweep_dict["mu_end"] = self.sweep.mu_end
            if self.sweep.mu_step is not None:
                sweep_dict["mu_step"] = self.sweep.mu_step
            if self.sweep.U_start is not None:
                sweep_dict["U_start"] = self.sweep.U_start
            if self.sweep.U_end is not None:
                sweep_dict["U_end"] = self.sweep.U_end
            if self.sweep.U_step is not None:
                sweep_dict["U_step"] = self.sweep.U_step
            result["sweep"] = sweep_dict
        return result
