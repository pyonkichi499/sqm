"""SQM カスタム例外モジュール

プロジェクト固有の例外階層を定義する。
"""

from __future__ import annotations

__all__ = [
    "SQMError",
    "FortranExecutionError",
    "BinaryFormatError",
    "ConfigurationError",
]


class SQMError(Exception):
    """SQM プロジェクトの基底例外"""


class FortranExecutionError(SQMError):
    """Fortran シミュレーションの実行失敗"""


class BinaryFormatError(SQMError):
    """Fortran バイナリファイルのフォーマットエラー"""


class ConfigurationError(SQMError):
    """設定の不整合・バリデーションエラー"""
