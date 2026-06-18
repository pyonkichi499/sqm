# CLAUDE.md

このファイルは、このリポジトリでコードを扱う際のClaude Code (claude.ai/code) への指針を提供します。

## プロジェクト概要

これは複素ランジュバン法を用いたボーズ・ハバード(BH)モデル計算のための量子力学シミュレーションプロジェクトです。計算物理にはFortran、オーケストレーションとデータ可視化にはPythonを組み合わせています。

## 開発コマンド

### ビルド
```bash
# Fortranコードのコンパイル
gfortran complex_Langevin_BH.f90

# ryeを使用してPython依存関係をインストール
rye sync
```

### シミュレーションの実行
```bash
# メイン計算スクリプトの実行
python calc_bh.py
```

## アーキテクチャ

このプロジェクトはハイブリッドアーキテクチャを採用しています：

1. **Fortranコア** (`complex_Langevin_BH.f90`): 量子シミュレーション用の複素ランジュバンアルゴリズムを実装
   - `a.out`実行ファイルにコンパイル
   - `params.dat`からパラメータを読み込み
   - シミュレーションデータを`.dat`ファイルに出力

2. **Pythonオーケストレーション** (`calc_bh.py`): メインドライバー
   - `wparams.py`を介してパラメータ設定を生成
   - 各パラメータセットに対してFortranバイナリを実行
   - `read_dat_mod.py`を使用して結果を収集
   - matplotlibでプロットを生成

3. **データフロー**:
   - `calc_bh.py` → `wparams.py` → `params.dat`
   - `params.dat` → `a.out` → `U={U}_s={s}.dat`
   - `U={U}_s={s}.dat` → `read_dat_mod.py` → `calc_bh.py`

## 主要パラメータ

シミュレーションでは以下の物理パラメータを使用：
- `U`: 相互作用強度（通常5-40）
- `mu`: 化学ポテンシャル（通常0.4*U）
- `Nsample`: 統計用のサンプル数
- `dtau`: 時間離散化
- `s`: 結合パラメータ

## パッケージ管理

このプロジェクトはPython依存関係の管理に`rye`を使用しています。Python依存関係：
- matplotlib (>=3.9.0)
- seaborn (>=0.13.2)
- numpy (>=1.26.4)
