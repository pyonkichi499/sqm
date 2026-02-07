# リファクタリング懸念点

## Critical: 正しさに影響する問題

### 1. ヘッダーの読み書きにずれがある (Fortran/Python間)

Fortran側 (`complex_Langevin_BH.f90:201`):
```fortran
write(20) Nx, U, mu, Ntau   ! int(4), double(8), double(8), int(4) = 24bytes
```

Python側 (`read_dat_mod.py:10-15`):
```python
header_dtype = np.dtype([
    ('head', '<i'),   # Fortranレコードマーカー (4bytes)
    ('Nx', '<i'),     # int (4bytes)
    ('U', '<f8'),     # double (8bytes)
    ('mu', '<f8'),    # double (8bytes)
    ('tail', '<i'),   # ← これはNtauを読んでいる。本来のレコードマーカーではない
])
```

Fortranのunformatted writeは `[reclen(4)] [data(24)] [reclen(4)]` = 32bytes を書くが、
Python側のdtypeは28bytesしか消費しない。結果:
- `tail` フィールドに入るのはNtau(=6)であり、末尾レコードマーカー(=24)ではない
- 未消費の4bytesが残り、後続のbodyレコード読み込みが4bytesずれる
- bodyデータが破損する可能性がある

**対処案**: header_dtypeにNtauフィールドを追加する。
```python
header_dtype = np.dtype([
    ('head', '<i'),
    ('Nx', '<i'),
    ('U', '<f8'),
    ('mu', '<f8'),
    ('Ntau', '<i'),   # 追加
    ('tail', '<i'),
])
```

### 2. 乱数シードが固定 (Fortran)

`complex_Langevin_BH.f90:234`:
```fortran
seed = 0
call random_seed(put=seed)
```

- 同一プロセス内の200サンプルは連続した乱数列を使うので互いに異なるが、
  並列実行時に異なるU値のプロセスが全く同じ乱数列からスタートする。
- 科学的な再現性のために意図的なら問題ないが、明示的に記述すべき。
- 本番用にはシステムクロックやプロセスIDから初期化する選択肢も必要。

### 3. `np.float` は非推奨 (Python 3.12+で削除済み)

`read_dat_mod.py:65-66`:
```python
corr_mean = np.zeros(Nx, np.float)   # → np.float64
corr_err = np.zeros(Nx, np.float)    # → np.float64
```

---

## Important: 保守性・設計上の問題

### 4. `readfile()` が3つの責務を持っている

`read_dat_mod.py:46-89` の `readfile()` は以下を全て行う:
- バイナリデータ読み込み
- 相関関数の計算
- プロット生成・ファイル保存

これにより:
- 「データだけ読みたい」「計算だけしたい」場合に使えない
- プロットの設定を変えるたびに関数全体を触る必要がある
- テストが困難

**対処案**: `read_dat()`, `compute_correlation()`, `plot_correlation()` に分離する。

### 5. `jackknife()` が O(n^2) で非効率

`read_dat_mod.py:29-43`:
```python
for i in range(n):
    for j in range(n):     # ← 全要素を毎回合計し直している
        if i != j:
            v += np.real(arr[j])
```

全体の合計を一度計算すれば O(n) にできる:
```python
total = np.sum(np.real(arr))
jk_mean = (total - np.real(arr)) / (n - 1)
```

### 6. パラメータが複数箇所にハードコードされている

| パラメータ | Fortran | wparams.py | read_dat_mod.py |
|-----------|---------|------------|-----------------|
| Ntau=6    | L8 (parameter) | - | L60 (ハードコード) |
| dtau=0.3  | - (params.datから) | L6 (ハードコード) | - |
| ds=0.3e-5 | - (params.datから) | L6 (ハードコード) | - |
| s_end=1.0 | - (params.datから) | L4 (ハードコード) | - |
| Nx=6      | L8 (parameter) | - | (ヘッダーから読む) |

Ntauは特に問題: Fortranが書き出しているのにPythonでは読まず `Ntau = 6` とハードコード。
懸念点1を修正すればヘッダーから読めるようになる。

### 7. ファイルハンドルが閉じられていない

`read_dat_mod.py:16`:
```python
fd = open(filename, 'r')
# ... 使用後にfd.close()がない
```

**対処案**: `with open(...) as fd:` にする。

### 8. ループ内で毎回関数定義している

`read_dat_mod.py:73-74`:
```python
for x in range(Nx):
    for i in range(N):
        def corr(a, a_ast, x):      # ← 毎イテレーションdefされる
            return a[0] * a_ast[x]
```

関数にする必要がなく、直接 `a[0] * a_ast[x]` で十分。
あるいはループ外に出す。

---

## Minor: クリーンアップ

### 9. `read_dat.py` が未使用のレガシーファイル

- `read_dat_mod.py` に機能が移されているが、古いファイルが残っている。
- さらに `read_dat.py:84` で未定義の `Ntau` を参照しており、実行するとクラッシュする。
- 削除してよい。

### 10. Fortranの未使用コード

- `do_langevin_loop()` (L136-163): コメントに「未使用」と書いてある。削除候補。
- main program内の未使用変数: `v`, `j`, `corrfunc` (L224-226)。

### 11. `pyproject.toml` が存在しないパスを参照

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/sqm"]       # ← src/sqm ディレクトリが存在しない
```

### 12. `.gitignore` が自身を無視している

```
.gitignore    # ← .gitignore自体がignore対象
```

---

## 全体構成の改善提案

### 現状のデータフロー
```
calc_bh.py
  → wparams.py (params.dat書き出し)
  → ./a.out (Fortranシミュレーション)
  → *.dat (バイナリ出力)
  → read_dat_mod.py (読み込み + 解析 + プロット)
```

### 提案: 責務の分離

```
config.py          ... パラメータ定義を一元管理 (dtau, ds等のデフォルト値)
wparams.py         ... params.dat書き出し (config.pyから値を受け取る)
calc_bh.py         ... オーケストレーション (並列実行制御)
io_fortran.py      ... Fortranバイナリの読み書き (read_dat + ヘッダー整合性)
analysis.py        ... 相関関数計算・jackknife (純粋な計算、I/O無し)
plot.py            ... 可視化 (計算結果を受け取ってプロットするだけ)
```

**利点**:
- 各モジュールが単一の責務を持つ
- パラメータ変更が1箇所で済む
- 解析コードをノートブック等から再利用できる
- ユニットテストが書きやすい

### 優先順位

修正を段階的に進める場合の推奨順:

1. **懸念点1 (ヘッダーずれ)** → データの正しさに直結
2. **懸念点3 (np.float)** → Python 3.12+で動かない
3. **懸念点4+5 (readfile分離 + jackknife高速化)** → 可読性・性能
4. **懸念点6 (パラメータ一元化)** → 保守性
5. 残りのクリーンアップ
