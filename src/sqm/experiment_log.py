"""実験ログ・メタデータモジュール

科学的再現性のための構造化された実験ログ機能を提供する。
"""

from __future__ import annotations

import json
import platform
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ExperimentLog:
    """実験のログとメタデータを管理するクラス。"""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    walltime_seconds: float = 0.0
    _start_time: float | None = field(default=None, repr=False)

    def set_parameters(self, **kwargs: Any) -> None:
        """実験パラメータを設定する。

        Args:
            **kwargs: パラメータ名と値のペア。
        """
        self.parameters.update(kwargs)

    @staticmethod
    def _run_git_command(args: list[str]) -> str | None:
        """Git コマンドを実行し、標準出力を返す。

        Args:
            args: git に渡す引数リスト。

        Returns:
            コマンドの標準出力（strip済み）。失敗時は None。
        """
        try:
            result = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def capture_git_info(self) -> None:
        """Gitリポジトリの情報をメタデータに記録する。

        Git リポジトリ外で実行された場合はエラーにならず、
        "unknown" を設定する。
        """
        git_hash = self._run_git_command(["rev-parse", "HEAD"])
        self.metadata["git_hash"] = git_hash if git_hash is not None else "unknown"

        git_branch = self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        self.metadata["git_branch"] = git_branch if git_branch is not None else "unknown"

        try:
            subprocess.run(
                ["git", "diff", "--quiet"],
                capture_output=True,
                check=True,
            )
            self.metadata["git_dirty"] = False
        except subprocess.CalledProcessError:
            self.metadata["git_dirty"] = True
        except FileNotFoundError:
            self.metadata["git_dirty"] = None

    def capture_environment(self) -> None:
        """実行環境の情報をメタデータに記録する。

        hostname, Python version, numpy version, platform 情報を取得する。
        """
        self.metadata["hostname"] = socket.gethostname()
        self.metadata["python_version"] = sys.version
        self.metadata["platform"] = platform.platform()

        try:
            import numpy as np

            self.metadata["numpy_version"] = np.__version__
        except ImportError:
            self.metadata["numpy_version"] = "not installed"

    def add_result(self, name: str, **kwargs: Any) -> None:
        """実験結果を記録する。

        Args:
            name: 結果の識別名（例: "U=20_mu=10"）。
            **kwargs: 結果データ（例: correlation, n_samples, n_failed）。
        """
        self.results[name] = dict(kwargs)

    def get_warnings(self) -> list[str]:
        """記録された結果に基づいて警告メッセージを生成する。

        失敗率が50%を超える結果がある場合に警告を返す。

        Returns:
            警告メッセージのリスト。
        """
        warnings: list[str] = []
        for name, result in self.results.items():
            n_samples = result.get("n_samples", 0)
            n_failed = result.get("n_failed", 0)
            total = n_samples + n_failed
            if total > 0 and n_failed / total > 0.5:
                failure_rate = n_failed / total * 100
                warnings.append(
                    f"High failure rate in '{name}': "
                    f"{failure_rate:.1f}% ({n_failed}/{total} 失敗)"
                )
        return warnings

    def to_dict(self) -> dict[str, Any]:
        """ログデータを辞書形式に変換する。

        Returns:
            ログの全データを含む辞書。
        """
        return {
            "timestamp": self.timestamp,
            "parameters": self.parameters,
            "metadata": self.metadata,
            "results": self.results,
            "walltime_seconds": self.walltime_seconds,
        }

    def save_json(self, path: str | Path) -> None:
        """ログデータをJSONファイルに保存する。

        Args:
            path: 出力先ファイルパス。
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_json(cls, path: str | Path) -> ExperimentLog:
        """JSONファイルからログデータを読み込む。

        Args:
            path: 読み込み元ファイルパス。

        Returns:
            読み込んだデータから復元した ExperimentLog インスタンス。
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            timestamp=data.get("timestamp", ""),
            parameters=data.get("parameters", {}),
            metadata=data.get("metadata", {}),
            results=data.get("results", {}),
            walltime_seconds=data.get("walltime_seconds", 0.0),
        )

    def summary(self) -> str:
        """人間が読みやすいサマリーレポートを生成する。

        Returns:
            実験パラメータ、メタデータ、結果、警告を含むレポート文字列。
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("Experiment Summary")
        lines.append("=" * 60)
        lines.append(f"Timestamp: {self.timestamp}")
        lines.append("")

        if self.parameters:
            lines.append("--- Parameters ---")
            for key, value in self.parameters.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        if self.metadata:
            lines.append("--- Metadata ---")
            for key, value in self.metadata.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        if self.results:
            lines.append("--- Results ---")
            for name, result in self.results.items():
                lines.append(f"  [{name}]")
                for key, value in result.items():
                    lines.append(f"    {key}: {value}")
            lines.append("")

        warnings = self.get_warnings()
        if warnings:
            lines.append("--- Warnings ---")
            for w in warnings:
                lines.append(f"  WARNING: {w}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def start_timer(self) -> None:
        """実行時間の計測を開始する。"""
        self._start_time = time.monotonic()

    def stop_timer(self) -> None:
        """実行時間の計測を停止し、walltime_seconds に記録する。

        start_timer() が呼ばれていない場合は walltime_seconds を 0.0 のままにする。
        """
        if self._start_time is not None:
            self.walltime_seconds = time.monotonic() - self._start_time
            self._start_time = None
