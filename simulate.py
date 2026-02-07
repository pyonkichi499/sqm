"""1つの(U, mu)パラメータ点に対するシミュレーション実行"""
import os
from subprocess import run

import click

import wparams


def run_one(U, mu, Nsample=200, outdir="output", **kw):
    """1シミュレーション実行。.datファイルパスを返す"""
    os.makedirs(outdir, exist_ok=True)
    datfilename = os.path.join(outdir, f"U={U},mu={mu}.dat")
    paramsfile = os.path.join(outdir, f"params_U={U}_mu={mu}.dat")

    wparams.write_params(mu, U, Nsample, datfilename, paramsfile=paramsfile, **kw)
    run(["./a.out", paramsfile], check=True)
    os.remove(paramsfile)
    return datfilename


@click.command()
@click.option("--U", "u_val", type=float, default=20, envvar="SQM_U")
@click.option("--mu", type=float, default=0, envvar="SQM_MU")
@click.option("--Nsample", "nsample", type=int, default=200, envvar="SQM_NSAMPLE")
@click.option("--outdir", default="output", envvar="SQM_OUTDIR")
def main(u_val, mu, nsample, outdir):
    # Cloud Run Jobs: CLOUD_RUN_TASK_INDEX から sweep パラメータを自動算出
    task_index = os.environ.get("CLOUD_RUN_TASK_INDEX")
    if task_index is not None:
        sweep = os.environ.get("SQM_SWEEP", "mu")  # "mu" or "U"
        start = float(os.environ.get("SQM_SWEEP_START", 0))
        step = float(os.environ.get("SQM_SWEEP_STEP", 2))
        val = start + int(task_index) * step
        if sweep == "mu":
            mu = val
        else:
            u_val = val

    click.echo(f"Running: U={u_val}, mu={mu}, Nsample={nsample}")
    datfile = run_one(u_val, mu, nsample, outdir)
    click.echo(f"Output: {datfile}")


if __name__ == "__main__":
    main()
