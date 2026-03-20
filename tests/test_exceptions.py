"""exceptions.py のテスト

カスタム例外階層の検証。
"""

from __future__ import annotations

from sqm.exceptions import (
    BinaryFormatError,
    ConfigurationError,
    FortranExecutionError,
    SQMError,
)


class TestExceptionHierarchy:
    """例外階層のテスト群"""

    def test_全カスタム例外はSQMErrorのサブクラス(self) -> None:
        assert issubclass(FortranExecutionError, SQMError)
        assert issubclass(BinaryFormatError, SQMError)
        assert issubclass(ConfigurationError, SQMError)

    def test_SQMErrorはExceptionのサブクラス(self) -> None:
        assert issubclass(SQMError, Exception)

    def test_例外にメッセージを設定できる(self) -> None:
        err = FortranExecutionError("simulation failed")
        assert str(err) == "simulation failed"
