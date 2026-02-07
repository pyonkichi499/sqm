## Summary
<!-- 変更の概要を1-3行で記述 -->


## Changes
<!-- 主な変更点を箇条書きで -->
-

## Motivation
<!-- なぜこの変更が必要か -->


## Test plan
<!-- テスト方法・確認項目 -->
- [ ] `make test-fortran` - Fortran tests passed
- [ ] `rye run pytest tests/ -v` - Python tests passed
- [ ] `rye run ruff check .` - Lint passed
- [ ] `rye run mypy src/sqm/` - Type check passed

## Affected areas
<!-- 該当する領域にチェック -->
- [ ] Fortran (simulation kernel)
- [ ] Python (orchestration / analysis)
- [ ] CI / build
- [ ] Documentation

## Notes
<!-- レビュアーへの補足事項があれば -->

