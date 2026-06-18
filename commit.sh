#!/usr/bin/env bash
#
# commit.sh - 現在の変更を論理単位ごとに分けてコミットするスクリプト
#
# 使い方:
#   ./commit.sh
#
# 動作:
#   変更を内容ごとにステージし、Conventional Commits 形式で個別にコミットする。
#   コミットメッセージは「1行目: type(scope): 概要」「3行目以降: 詳細」とする。
#
set -euo pipefail

# リポジトリのルートへ移動
cd "$(git rev-parse --show-toplevel)"

echo "=== 現在のブランチ ==="
git branch --show-current
echo

# ------------------------------------------------------------------
# コミット用ヘルパー
#   $1: 件名 (type(scope): 概要)
#   $2: 本文 (3行目以降の詳細)
#   $3..: 対象ファイル
# ------------------------------------------------------------------
commit_files() {
    local subject="$1"
    local body="$2"
    shift 2
    local files=("$@")

    # 対象ファイルのうち、実際に変更があるものだけ抽出
    local changed=()
    for f in "${files[@]}"; do
        if [ -n "$(git status --porcelain -- "$f")" ]; then
            changed+=("$f")
        fi
    done

    if [ ${#changed[@]} -eq 0 ]; then
        echo "スキップ: 変更なし -> $subject"
        echo
        return 0
    fi

    echo "----------------------------------------------------------"
    echo "コミット: $subject"
    echo "対象ファイル:"
    printf '  %s\n' "${changed[@]}"
    echo "----------------------------------------------------------"

    git add -- "${changed[@]}"
    # -m を2つ渡すと件名と本文が空行で区切られる
    git commit -m "$subject" -m "$body"
    echo
}

# ------------------------------------------------------------------
# コミット1: Claude Code の権限設定
# ------------------------------------------------------------------
commit_files \
"chore(claude): add git push and rev-list to allowed permissions" \
"Claude Code のローカル権限設定 (.claude/settings.local.json) に以下を追加:
- Bash(git push:*): ブランチのプッシュを許可
- Bash(git rev-list *): コミット数の集計などに使用

これにより push と rev-list 実行時に都度の許可確認が不要になる。" \
    ".claude/settings.local.json"

# ------------------------------------------------------------------
# コミット2: npm ロックファイル
# ------------------------------------------------------------------
commit_files \
"chore: add npm package-lock.json" \
"npm 経由で導入したツールの依存関係を固定するため package-lock.json を追加。
現状 packages は空だが、今後の npm 依存追加時にロックファイルとして機能する。" \
    "package-lock.json"

echo "=== 完了しました。直近のコミット履歴 ==="
git log --oneline -5
