"""Fortran バイナリ I/O モジュール

Fortran シミュレーションとのデータ入出力を担当する。
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def read_dat(filename: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Fortranバイナリファイルからヘッダーとボディを読み込む。

    Parameters
    ----------
    filename : str | Path
        読み込むバイナリファイルのパス

    Returns
    -------
    Tuple[np.ndarray, np.ndarray]
        (header, body) のタプル

    Raises
    ------
    FileNotFoundError
        ファイルが存在しない場合
    ValueError
        ファイルが空の場合、またはヘッダーの Nx が不正な場合
    """
    filepath = Path(filename)

    if not filepath.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {filepath}")

    if filepath.stat().st_size == 0:
        raise ValueError(f"ファイルが空です: {filepath}")

    head, tail = ("head", "<i"), ("tail", "<i")
    header_dtype = np.dtype([head, ("Nx", "<i"), ("U", "<f8"), ("mu", "<f8"), ("Ntau", "<i"), tail])

    with open(filepath, "rb") as fd:
        header = np.fromfile(fd, dtype=header_dtype, count=1)

        if len(header) == 0:
            raise ValueError(f"ヘッダーが空です: {filepath}")

        Nx = int(header[0]["Nx"])

        if not 1 <= Nx <= 1000:
            raise ValueError(f"Nx の値が不正です (1-1000 の範囲外): {Nx}")

        body_dtype = np.dtype([head, ("a", f"<{Nx}c16"), ("a_ast", f"<{Nx}c16"), tail])
        body = np.fromfile(fd, dtype=body_dtype, count=-1)

    logger.debug("ヘッダー読み込み完了: Nx=%d", Nx)
    return header, body


def write_params(
    mu: float,
    U: float,
    Nsample: int,
    filename: str,
    paramsfile: str | Path = "params.dat",
    dtau: str = "0.3d0",
    ds: str = "0.3d-5",
    s_end: str = "1d0",
    seed: int | None = None,
) -> None:
    """Fortran NAMELIST形式のパラメータファイルを生成する。

    Args:
        mu: 化学ポテンシャル
        U: 相互作用の強さ
        Nsample: サンプリング数
        filename: 出力データファイル名
        paramsfile: パラメータファイルの出力パス
        dtau: 虚時間の刻み幅 (Fortran倍精度表記)
        ds: フロー方程式のステップ幅 (Fortran倍精度表記)
        s_end: フロー方程式の終了値 (Fortran倍精度表記)
        seed: 乱数シード値 (None の場合は Fortran 側でシステムエントロピーを使用)
    """
    if seed is not None:
        logger.warning(
            "seed=%d が指定されましたが、現在の Fortran コードはシード制御に"
            "未対応です。Fortran 側の NAMELIST にシード変数を追加してください。",
            seed,
        )

    paramsfile = Path(paramsfile)
    paramsfile.parent.mkdir(parents=True, exist_ok=True)

    with open(paramsfile, "w") as f:
        f.write(
            f"&params\n"
            f"mu = {mu}\n"
            f"U = {U}\n"
            f"dtau = {dtau}\n"
            f"ds = {ds}\n"
            f"s_end = {s_end}\n"
            f'datfilename = "{filename}"\n'
            f"/\n"
            f"&sampling_setting\n"
            f"Nsample = {int(Nsample)}\n"
            f"/\n"
        )
