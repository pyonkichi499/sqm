"""設定管理モジュール

シミュレーションパラメータを一元管理するための dataclass 群と、
YAML / JSON によるシリアライゼーションを提供する。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# =============================================================================
# Round 1: SimulationConfig
# =============================================================================


@dataclass
class SimulationConfig:
    """Fortran シミュレーションの基本パラメータ"""

    dtau: str = "0.3d0"
    ds: str = "0.3d-5"
    s_end: str = "1d0"
    Nsample: int = 200


# =============================================================================
# Round 2: PathConfig
# =============================================================================


@dataclass
class PathConfig:
    """ファイルパス設定"""

    output_dir: Path = field(default_factory=lambda: Path("."))
    figures_dir: Path = field(default_factory=lambda: Path("./figures"))
    fortran_binary: Path = field(default_factory=lambda: Path("./a.out"))

    def __post_init__(self) -> None:
        # 文字列が渡された場合に Path へ変換する
        self.output_dir = Path(self.output_dir)
        self.figures_dir = Path(self.figures_dir)
        self.fortran_binary = Path(self.fortran_binary)


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

    def sweep_values(self) -> list[float]:
        """スイープ値のリストを返す"""
        if self.sweep_param == "mu":
            assert self.mu_start is not None
            assert self.mu_end is not None
            assert self.mu_step is not None
            values: list[float] = []
            current = self.mu_start
            while current < self.mu_end:
                values.append(current)
                current = round(current + self.mu_step, 10)
            return values
        else:
            assert self.U_start is not None
            assert self.U_end is not None
            assert self.U_step is not None
            values = []
            current = self.U_start
            while current < self.U_end:
                values.append(current)
                current = round(current + self.U_step, 10)
            return values


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
            assert self.base_seed is not None
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
            data: dict[str, Any] = yaml.safe_load(f) or {}
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
            data: dict[str, Any] = json.load(f)
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
