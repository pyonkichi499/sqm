"""1つの(U, mu)パラメータ点に対するシミュレーション実行"""
import os
import argparse
from subprocess import run

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


def main():
    parser = argparse.ArgumentParser(description="1点のシミュレーション実行")
    parser.add_argument("--U", type=float,
                        default=float(os.environ.get("SQM_U", 20)))
    parser.add_argument("--mu", type=float,
                        default=float(os.environ.get("SQM_MU", 0)))
    parser.add_argument("--Nsample", type=int,
                        default=int(os.environ.get("SQM_NSAMPLE", 200)))
    parser.add_argument("--outdir",
                        default=os.environ.get("SQM_OUTDIR", "output"))
    args = parser.parse_args()

    # Cloud Run Jobs: CLOUD_RUN_TASK_INDEX から sweep パラメータを自動算出
    task_index = os.environ.get("CLOUD_RUN_TASK_INDEX")
    if task_index is not None:
        sweep = os.environ.get("SQM_SWEEP", "mu")  # "mu" or "U"
        start = float(os.environ.get("SQM_SWEEP_START", 0))
        step = float(os.environ.get("SQM_SWEEP_STEP", 2))
        val = start + int(task_index) * step
        if sweep == "mu":
            args.mu = val
        else:
            args.U = val

    print(f"Running: U={args.U}, mu={args.mu}, Nsample={args.Nsample}")
    datfile = run_one(args.U, args.mu, args.Nsample, args.outdir)
    print(f"Output: {datfile}")


if __name__ == "__main__":
    main()
