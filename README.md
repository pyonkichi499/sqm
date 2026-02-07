# SQM - Complex Langevin Simulation

## 概要

3次元格子上のBose-Hubbardモデルに対するComplex Langevin法によるシミュレーション。
符号問題を回避するため複素拡張されたLangevin方程式を用いて、ボソン場の空間相関関数を計算する。

### 物理的背景

Bose-Hubbardモデルは、光格子中のボソン原子系を記述する基本的な模型である。
有限化学ポテンシャル ($\mu \neq 0$) の場合、作用が複素数となりモンテカルロ法で
直接シミュレーションできない「符号問題」が生じる。本プロジェクトでは、
Complex Langevin法を用いてこの符号問題を回避し、空間相関関数
$\langle a_0 a_i^* \rangle$ を計算する。

### 主な機能

- 3次元格子 ($N_x \times N_y \times N_z = 6 \times 6 \times 6$) 上のComplex Langevin シミュレーション
- RK2 (Heun法) による時間発展で高精度な数値積分を実現
- Uまたは$\mu$のパラメータスイープ（並列実行対応）
- Jackknife法による統計誤差推定
- 自己相関解析によるthermalization検出と有効サンプル数の計算
- 相関関数のプロット自動生成
- YAML/JSON設定ファイルによるパラメータ管理
- 実験ログ・メタデータの構造化記録

## セットアップ

### 前提条件

- Python >= 3.12
- gfortran (Fortranコンパイラ)
- [Rye](https://rye.astral.sh/) (Pythonパッケージマネージャ)

### インストール

1. リポジトリをクローンする:

```bash
git clone <repository-url>
cd sqm
```

2. Python依存パッケージをインストールする:

```bash
rye sync
```

3. Fortranコードをコンパイルする:

```bash
make
```

## 使い方

### Fortranコードのコンパイル

```bash
# 最適化ビルド
make

# デバッグビルド（境界チェック、バックトレース有効）
make a_debug.out

# ビルド成果物のクリーンアップ
make clean
```

### パラメータスイープの実行

#### CLIによる実行

`sqm sweep` コマンドでパラメータスイープを実行する。U または $\mu$ の一方を固定し、もう一方をスイープする。

```bash
# mu をスイープ（U=20 固定）
rye run sqm sweep --u 20 --mu-start 0 --mu-end 20 --mu-step 2 --nsample 200

# U をスイープ（mu=10 固定）
rye run sqm sweep --mu 10 --u-start 0 --u-end 30 --u-step 5 --nsample 200

# ワーカー数を指定して並列実行
rye run sqm sweep --u 20 --mu-start 0 --mu-end 20 --mu-step 2 --nsample 200 --workers 4

# ドライラン（実行計画のみ表示）
rye run sqm sweep --u 20 --mu-start 0 --mu-end 20 --mu-step 2 --nsample 200 --dry-run

# 詳細ログを有効にする
rye run sqm sweep --u 20 --mu-start 0 --mu-end 20 --mu-step 2 --nsample 200 -v
```

#### 設定ファイルによる管理

```bash
# デフォルト設定ファイルを生成
rye run sqm config init

# 設定ファイルの内容を確認
rye run sqm config show

# カスタムパスに設定ファイルを生成
rye run sqm config init --output my_config.yaml
```

設定ファイル (`config.yaml`) の例:

```yaml
simulation:
  dtau: "0.3d0"      # 虚時間の刻み幅
  ds: "0.3d-5"       # Langevinステップ幅
  s_end: "1d0"       # Langevin時間の終了値
  Nsample: 200       # サンプリング数

paths:
  output_dir: "."
  figures_dir: "./figures"
  fortran_binary: "./a.out"

sweep:
  U: 20.0             # 固定値
  mu_start: 0.0       # スイープ開始
  mu_end: 20.0        # スイープ終了
  mu_step: 2.0        # スイープ刻み

seed:
  mode: "system"       # "system", "fixed", "hybrid"
  base_seed: null
```

### テスト実行

```bash
# 全テスト（Fortran + Python）を実行
make test

# Fortranテストのみ
make test-fortran

# Pythonテストのみ
make test-python

# Pythonテストを詳細出力で実行
rye run pytest tests/ -v

# 特定のテストファイルを実行
rye run pytest tests/test_read_dat_mod.py -v

# 遅いテストを除外して実行
rye run pytest tests/ -v -m "not slow"
```

### コード品質チェック

```bash
# リンター
rye run ruff check .

# フォーマッター
rye run ruff format .

# 型チェック
rye run mypy .
```

## プロジェクト構造

```
sqm/
├── src/sqm/                    # Python パッケージ
│   ├── __init__.py
│   ├── cli.py                  # Click CLI エントリポイント (sweep, config サブコマンド)
│   ├── config.py               # 設定管理 (dataclass + YAML/JSON シリアライゼーション)
│   ├── read_dat_mod.py         # Fortranバイナリ I/O、Jackknife解析、相関関数計算・プロット
│   ├── autocorrelation.py      # 自己相関解析ツール (FFTベース、Sokalウィンドウ法)
│   ├── calc_bh.py              # シミュレーションオーケストレーション (並列実行制御)
│   ├── wparams.py              # Fortran NAMELIST形式パラメータファイル生成
│   └── experiment_log.py       # 実験ログ・メタデータ管理 (Git情報、環境情報の記録)
│
├── fortran/                    # Fortranシミュレーションコード
│   ├── functions_module.f90    # 物理カーネル (da, da_ast, RK2ソルバー, Box-Muller, I/O)
│   ├── complex_Langevin_BH.f90 # メインプログラム (パラメータ読み込み、サンプリングループ)
│   └── test_functions.f90      # Fortranユニットテスト (11テストケース)
│
├── tests/                      # Pythonテストスイート
│   ├── __init__.py
│   ├── conftest.py             # pytest設定 (フィクスチャ、乱数シード固定)
│   ├── test_autocorrelation.py
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_experiment_log.py
│   ├── test_read_dat_mod.py
│   ├── test_wparams.py
│   └── fixtures/               # テスト用データファイル
│
├── Makefile                    # ビルド・テスト・リントコマンド
├── pyproject.toml              # Python プロジェクト設定 (Rye, Ruff, mypy, pytest)
└── .gitignore
```

## アルゴリズム

### Complex Langevin法

Bose-Hubbardモデルの作用 $S[a, a^*]$ に対するComplex Langevin方程式:

$$\frac{da}{ds} = -\frac{\delta S}{\delta a^*} + \eta(s)$$

$$\frac{da^*}{ds} = -\frac{\delta S}{\delta a} + \eta^*(s)$$

ここで $\eta(s)$ はガウシアンホワイトノイズで、$\langle \eta(s) \eta^*(s') \rangle = 2\delta(s - s')$ を満たす。

#### ドリフト項 (da, da_ast)

`functions_module.f90` の `da()` 関数は以下を計算する:

$$\text{da} = 2\left[\frac{a(\tau+1, x) - a(\tau-1, x)}{2\Delta\tau} + \sum_{i=1}^{6} a(\tau, \text{nn}_i(x)) - U a^* a^2 + \mu a\right]$$

- 虚時間方向 ($\tau$) の差分は周期境界条件
- 空間方向は3次元格子上の6つの最近接サイトの和
- 非線形項 $-U a^* a^2$ がBose-Hubbardの相互作用を表現

#### RK2 (Heun法) による時間発展

2次のRunge-Kutta法（Heun法）で高精度に時間発展させる:

1. **第1パス（予測子）**: 中間点 $a_\text{mid}$ を計算
   $$a_\text{mid} = a + K_1 \cdot ds + \sigma \cdot dW$$

2. **第2パス（修正子）**: 最終値を計算
   $$a_\text{next} = a + \frac{1}{2}(K_1 + K_2) \cdot ds + \sigma \cdot dW$$

   ここで $K_1 = \text{da}(a)$, $K_2 = \text{da}(a_\text{mid})$, $\sigma = \sqrt{2 \cdot ds / d\tau}$

各ステップでNaN/Infの検出を行い、発散した場合はサンプルをスキップする。

#### Box-Muller法によるガウシアンノイズ生成

一様乱数 $(X, Y)$ から複素ガウシアンノイズ $dW$ を生成:

$$dW = \sqrt{-2\ln X} \cdot (\cos 2\pi Y + i \sin 2\pi Y)$$

cos と sin の両方を使うことで、1組の一様乱数から複素ノイズの実部・虚部を同時に生成する。

### 統計解析

#### Jackknife法による誤差推定

O(n) の効率的なJackknife法で、相関関数の平均値と統計誤差を推定する:

1. 全体平均: $\bar{x} = \frac{1}{n}\sum_i x_i$
2. Leave-one-out 平均: $\bar{x}_{(i)} = \frac{T - x_i}{n-1}$ （$T = \sum_i x_i$）
3. 誤差: $\sigma_\text{JK} = \sqrt{(n-1)\text{Var}(\bar{x}_{(i)})}$

#### 自己相関解析

`autocorrelation.py` モジュールが提供する機能:

- **自己相関関数**: FFTを用いた高速計算（$O(n \log n)$）
- **積分自己相関時間** ($\tau_\text{int}$): Sokalの自動ウィンドウ法で打ち切りラグを決定
- **有効サンプル数**: $N_\text{eff} = N / (2\tau_\text{int})$
- **Thermalization検出**: Geweke診断に着想を得たウィンドウベースの手法
- **データ間引き**: 自己相関時間に基づく自動間引き
- **補正済み誤差**: $\sigma_\text{corrected} = \sigma \sqrt{2\tau_\text{int} / N}$

## 開発ガイド

### TDDアプローチ

本プロジェクトはTest-Driven Development (TDD) に従って開発されている:

1. **Red**: まず失敗するテストを書く
2. **Green**: テストが通る最小限の実装を行う
3. **Refactor**: コードを整理する

テスト名は日本語で記述し、テストの意図を明確にする:

```python
def test_空のファイルは例外を送出する():
    ...

def test_ヘッダーのNxが正しく読み込まれる():
    ...
```

### テストの実行方法

```bash
# 全テスト
make test

# Pythonテストのみ（詳細出力）
rye run pytest tests/ -v

# カバレッジ付き
rye run pytest tests/ -v --cov=src/sqm
```

### コード品質ツール

| ツール | コマンド | 用途 |
|--------|---------|------|
| Ruff (lint) | `rye run ruff check .` | コードスタイル、潜在的なバグの検出 |
| Ruff (format) | `rye run ruff format .` | コードフォーマット |
| mypy | `rye run mypy .` | 静的型チェック |

### コーディング規約

- **Python**: 4スペースインデント、型ヒント必須、f-string使用
- **Fortran**: Fortran 2018標準、`iso_fortran_env` 使用、`implicit none` 必須
- **行長**: Python 100文字 (`pyproject.toml` の `tool.ruff` で設定)
- **テスト名**: 日本語で記述（例: `test_ユーザーが存在しない場合はエラーを返す`）

## ライセンス

本プロジェクトはプライベートリポジトリです。
