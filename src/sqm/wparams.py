from pathlib import Path


def write_params(
    mu: float,
    U: float,
    Nsample: int,
    filename: str,
    paramsfile: str | Path = "params.dat",
    dtau: str = "0.3d0",
    ds: str = "0.3d-5",
    s_end: str = "1d0",
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
    """
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
