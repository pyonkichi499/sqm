# CI/CD 要件

## 1. CI (Continuous Integration)

### トリガー
- `push` (全ブランチ)
- `pull_request` (main/master向け)

### ジョブ

#### Fortran テスト
- gfortranインストール
- `make test` (test_functions.f90 の31テスト)

#### Python テスト
- Python 3.12 + 依存パッケージ (numpy, matplotlib, seaborn, pytest)
- `python -m pytest tests/ -v`
- Fortranバイナリ不要 (simulate.run_oneはmockされている)

#### (将来) lint
- ruff / flake8 によるコードチェック

### 環境
- GitHub Actions `ubuntu-latest`
- gfortran: `apt-get install gfortran`
- Python: `actions/setup-python@v5` → `pip install`

### 注意点
- `.github/workflows/` へのpushにはworkflows権限が必要
- Fortranテストの `-O2` フラグは必須 (最適化でのみ発生するバグの検知)

## 2. CD (Continuous Delivery)

### Docker イメージビルド
- トリガー: `main` ブランチへのマージ (タグpush時でも可)
- マルチステージビルド: テスト通過後に本番イメージ生成
- レジストリ: GCR (`gcr.io/$PROJECT_ID/sqm`) or Artifact Registry

### Cloud Run Jobs デプロイ
- イメージpush後に `gcloud run jobs update` で反映
- 環境変数 (SQM_U, SQM_SWEEP_*, etc.) はジョブ定義側で管理

## 3. ワークフロー例 (GitHub Actions)

```yaml
name: CI
on:
  push:
  pull_request:
    branches: [main]

jobs:
  fortran-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y gfortran
      - run: make test

  python-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install numpy matplotlib seaborn pytest
      - run: python -m pytest tests/ -v
```

## 4. 優先度

| 項目 | 優先度 | 理由 |
|------|--------|------|
| Python単体テスト (CI) | 高 | 計算ロジックの回帰防止 |
| Fortranテスト (CI) | 高 | 数値計算のバグ検知 |
| Dockerイメージビルド (CD) | 中 | クラウド実行時に必要 |
| Cloud Runデプロイ (CD) | 低 | 手動デプロイでも十分回せる段階 |
| lint | 低 | コード規模が小さい |
