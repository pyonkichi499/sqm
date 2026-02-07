# リファクタリング記録

全12項目を修正済み。以下は実施内容の記録。

## Critical (修正済み)

| # | 問題 | 対処 |
|---|------|------|
| 1 | header dtype にNtauフィールドが無く、bodyが4bytesずれていた | `read_dat_mod.py`: Ntauフィールド追加 |
| 2 | 乱数シード固定 (`seed=0`) で並列時に同一列 | `complex_Langevin_BH.f90`: `call random_seed()` でシステムエントロピー使用 |
| 3 | `np.float` が Python 3.12+ で削除済み | `read_dat_mod.py`: `np.float64` に置換 |

## Important (修正済み)

| # | 問題 | 対処 |
|---|------|------|
| 4 | `readfile()` が読み込み・計算・プロットの3責務 | `read_dat()`, `compute_correlation()`, `plot_correlation()` に分離 |
| 5 | `jackknife()` が O(n^2) | O(n) に書き換え (`total - arr[i]`) |
| 6 | パラメータのハードコード (Ntau, dtau, ds, s_end) | Ntauはヘッダーから読取り、dtau/ds/s_endは `wparams.py` の引数に |
| 7 | ファイルハンドル未クローズ | `with open()` に統一 |
| 8 | ループ内で毎回関数定義 | インライン式 `a[0] * a_ast[x]` に置換 |

## Minor (修正済み)

| # | 問題 | 対処 |
|---|------|------|
| 9 | `read_dat.py` が未使用 | 削除 |
| 10 | Fortranの未使用コード (`do_langevin_loop`, 変数) | 削除 |
| 11 | `pyproject.toml` が存在しない `src/sqm` を参照 | `.` に修正 |
| 12 | `.gitignore` が自身を無視 | 該当行を削除 |
