# CLAUDE-JP.md - SQM プロジェクト指示書

## プロジェクト概要

3次元格子上のBose-Hubbardモデルに対するComplex Langevinシミュレーション。Fortran + Python のハイブリッドアーキテクチャで、Fortranが数値シミュレーションカーネルを、Pythonがオーケストレーション・解析・可視化を担当する。

有限化学ポテンシャルで生じる符号問題を回避するためComplex Langevin法を用い、空間相関関数 $\langle a_0 a_i^* \rangle$ を計算する。

## 主要アーキテクチャ

- **Fortran**: 数値シミュレーションカーネル（RK2ソルバー、Complex Langevin力学、Box-Mullerノイズ生成、バイナリI/O）
- **Python**: パラメータスイープ制御、Fortranバイナリデータ入出力、統計解析（Jackknife、自己相関）、可視化、CLIインターフェース、設定管理

### データフロー

```
CLI (cli.py) / calc_bh.py
  -> wparams.py          (Fortran NAMELIST形式でparams.datを書き出し)
  -> ./a.out params.dat  (Fortranシミュレーション実行、*.datバイナリを出力)
  -> read_dat_mod.py     (Fortranの非整形バイナリを読み込み、相関関数を計算)
  -> autocorrelation.py  (統計解析: thermalization検出、有効サンプル数)
  -> matplotlib plot     (figures/*.pngとして保存)
```

### Fortranバイナリ形式

Fortranシミュレーションは非整形シーケンシャルファイルを出力する:
- **ヘッダーレコード**: `[reclen(4)] [Nx(i4)] [U(f8)] [mu(f8)] [Ntau(i4)] [reclen(4)]` = 32バイト
- **ボディレコード**: `[reclen(4)] [a(Nx*c16)] [a_ast(Nx*c16)] [reclen(4)]` (サンプルごと)

Pythonでは `numpy.fromfile()` と構造化dtypeを用いて、Fortranのレコードマーカー（`head`/`tail`フィールド）を含めて読み込む。

## ビルド・テストコマンド

```bash
make                          # Fortranコードをコンパイル（最適化ビルド）
make a_debug.out              # デバッグフラグ付きコンパイル（-g -fcheck=all -fbacktrace）
make test                     # 全テスト実行（Fortran + Python）
make test-fortran             # Fortranテストのみ実行
make test-python              # Pythonテストのみ実行（rye run pytest tests/ -v）
make lint                     # Pythonコードのリント（rye run ruff check .）
make format                   # Pythonコードのフォーマット（rye run ruff format .）
make type-check               # Pythonコードの型チェック（rye run mypy .）
make clean                    # ビルド成果物とキャッシュを削除
rye run pytest tests/ -v      # Pythonテストを詳細出力で実行
rye run pytest tests/ -v --cov=src/sqm  # カバレッジ付きで実行
```

## コーディング規約

### Python
- インデントは4スペース
- 全関数シグネチャに型ヒントを付ける
- 文字列フォーマットにはf-stringを使用
- 行長: 100文字（pyproject.tomlの `[tool.ruff]` で設定）
- forward referenceには `from __future__ import annotations` を使用
- 文字列パスではなく `pathlib.Path` を使用
- ロギングは `logging.getLogger(__name__)` で行う

### Fortran
- Fortran 2018標準（`-std=f2018`）
- ポータブルな型のために `iso_fortran_env` を使用（`real64`, `int32`）
- NaN/Inf検出に `ieee_arithmetic` を使用
- 全スコープで `implicit none`
- パラメータファイルI/OにNAMELISTを使用

### テスト
- テスト名は日本語で記述: `test_{シナリオの説明}`
  - 例: `test_空のファイルは例外を送出する()`
  - 例: `test_ヘッダーのNxが正しく読み込まれる()`
- TDD: Red-Green-Refactor サイクル
- 全テストで乱数シードを固定（conftest.pyのautouseフィクスチャで `np.random.seed(42)`）
- Fortranテストは独自のアサーションフレームワークを使用（`assert_eq_int`, `assert_near` 等）

## 主要ファイル

### Python (src/sqm/)
- `cli.py` - Click CLIエントリポイント。`sweep` と `config` のコマンドグループを持つ
- `config.py` - ネストされたdataclassによる設定管理（`Config`, `SimulationConfig`, `PathConfig`, `SweepConfig`, `SeedConfig`）。YAML/JSONシリアライゼーション対応
- `read_dat_mod.py` - FortranバイナリI/O（`read_dat`）、Jackknife解析（`jackknife`）、相関関数計算（`compute_correlation`）、プロット（`plot_correlation`）、レガシーラッパー（`readfile`）
- `autocorrelation.py` - 統計解析ツール: FFTベースの自己相関、積分自己相関時間（Sokalウィンドウ法）、有効サンプル数、thermalization検出（Geweke診断着想）、データ間引き、補正済み誤差推定
- `calc_bh.py` - `ProcessPoolExecutor` による並列パラメータスイープのオーケストレーション
- `wparams.py` - Fortran NAMELISTパラメータファイルの生成（`&params` と `&sampling_setting`）
- `experiment_log.py` - 構造化された実験ログ。Git情報取得、環境メタデータ、JSON永続化、警告生成機能

### Fortran (fortran/)
- `functions_module.f90` - コア物理モジュール:
  - 格子セットアップ: `make_pos_arrays()`, `set_nn()`（3次元周期格子の最近接テーブル）
  - ドリフト項: `da()`, `da_ast()`（Bose-Hubbard作用の導関数）
  - RK2ソルバー: `do_langevin_loop_RK()`（NaN/Inf検出付きHeun法）
  - ノイズ: `set_dw()`（Box-Muller法による複素ガウシアンノイズ）
  - I/O: `write_header()`, `write_body()`
  - 格子パラメータ: `Ntau=6`, `Nx=Ny=Nz=6`, `Dx=216`
- `complex_Langevin_BH.f90` - メインプログラム: NAMELISTパラメータ読み込み、サンプリングループ、バイナリ出力
- `test_functions.f90` - Fortranユニットテスト（11テストサブルーチン）

### 設定ファイル
- `pyproject.toml` - Ryeプロジェクト設定、Ruffリントルール、mypy設定、pytestマーカー
- `Makefile` - ビルド・テスト自動化

## 重要な注意事項

- Fortranは非整形（バイナリ）I/Oを使用し、レコードマーカーが付く。Python側の読み込みでは、gfortranが各レコードの前後に書き込む4バイトのレコード長マーカーを考慮する必要がある。
- シミュレーションパラメータ `dtau`, `ds`, `s_end` はFortranの倍精度リテラル文字列（例: `"0.3d0"`, `"0.3d-5"`）として渡される。これはFortranが読み込むNAMELISTファイルに直接書き込まれるため。
- `calc_bh.py` の `ProcessPoolExecutor` による並列実行では、各ワーカープロセスが独立した乱数シードを取得する（`call random_seed()` によるシステムエントロピー使用）。
- `SeedConfig` は3つのモードをサポート: `"system"`（OSエントロピー）、`"fixed"`（決定論的）、`"hybrid"`（base_seed + process_id）。
