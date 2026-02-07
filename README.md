# sqm - Bose-Hubbard model simulation

複素ランジュバン法による Bose-Hubbard モデルのシミュレーション。
3次元立方格子 (6x6x6, 周期境界条件) 上でのボソン系の空間相関関数を計算する。

## セットアップ

### 前提条件

- Python 3.10+
- gfortran
- make

### ローカル環境 (rye)

```bash
# rye で仮想環境を構築
rye sync

# Fortran バイナリのビルド
make build

# テスト
make test
```

### Docker

```bash
docker build -t sqm .
```

## 使い方

### 1. ローカル並列スイープ

`sweep.py` の設定を編集してパラメータを定義し、ローカルで並列実行する。

```python
# sweep.py の設定部分
U = 20                       # 固定
mu = np.arange(0, 20, 2)    # スイープ
```

```bash
# rye 環境
rye run sqm-sweep

# または直接
python sweep.py
# または
make run
```

出力: `output/*.dat` (シミュレーションデータ) + `output/*.png` (スイープ図)

### 2. 1点だけ実行

デバッグや単発実行に。

```bash
# CLI 引数
python simulate.py --U 20 --mu 4 --Nsample 200

# 環境変数
SQM_U=20 SQM_MU=4 python simulate.py
```

### 3. 既存データからプロットだけやり直す

シミュレーション済みの `.dat` からプロットを再生成する。

```bash
python collect.py output/
```

### 4. Docker (ローカル)

```bash
# 1点実行
docker run -v ./output:/app/output sqm \
  python simulate.py --U 20 --mu 4

# スイープ (コンテナ内で並列)
docker run -v ./output:/app/output sqm \
  python sweep.py

# テスト
docker run sqm make test
```

### 5. Cloud Run Jobs (GCP)

パラメータ点ごとに1コンテナを起動し、クラウドで大規模並列実行する。

```bash
# イメージをビルド・プッシュ
docker build -t gcr.io/PROJECT/sqm .
docker push gcr.io/PROJECT/sqm

# Job 作成 (mu=0,2,4,...,18 の10点スイープ, U=20固定)
gcloud run jobs create sqm-sweep \
  --image=gcr.io/PROJECT/sqm \
  --tasks=10 \
  --set-env-vars=SQM_U=20,SQM_SWEEP=mu,SQM_SWEEP_START=0,SQM_SWEEP_STEP=2

# 実行
gcloud run jobs execute sqm-sweep

# 結果を GCS からダウンロード後にプロット
python collect.py output/
```

環境変数:

| 変数 | 説明 | デフォルト |
|------|------|-----------|
| `SQM_U` | U の値 | 20 |
| `SQM_MU` | mu の値 | 0 |
| `SQM_NSAMPLE` | サンプル数 | 200 |
| `SQM_OUTDIR` | 出力ディレクトリ | output |
| `SQM_SWEEP` | スイープ対象 (`mu` or `U`) | mu |
| `SQM_SWEEP_START` | スイープ開始値 | 0 |
| `SQM_SWEEP_STEP` | スイープ刻み幅 | 2 |
| `CLOUD_RUN_TASK_INDEX` | Cloud Run Jobs が自動設定 | - |

## ファイル構成

```
simulate.py              1点の(U, mu)シミュレーション実行
sweep.py                 ローカル並列パラメータスイープ
collect.py               結果集約・プロット生成
wparams.py               Fortran用パラメータファイル書き出し
read_dat_mod.py          Fortranバイナリ読み込み・相関関数計算

functions_module.f90     Fortranモジュール (物理計算)
complex_Langevin_BH.f90  Fortranメインプログラム
test_functions.f90        Fortranユニットテスト (31テスト)

Makefile                 ビルド・テスト・実行
Dockerfile               コンテナイメージ
pyproject.toml           Python依存関係 (rye)
```

## Make ターゲット

| コマンド | 説明 |
|---------|------|
| `make build` | Fortran バイナリのコンパイル |
| `make test` | ユニットテスト実行 (31テスト) |
| `make run` | ローカルスイープ実行 |
| `make clean` | ビルド成果物の削除 |
| `make cleanall` | ビルド成果物 + output/ の削除 |
