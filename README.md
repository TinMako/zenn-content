# zenn-content

[Zenn](https://zenn.dev) の GitHub 連携リポジトリ。Nagi/Mio（自律型 FX 取引システム）開発の技術記事を管理する。

## Zenn との連携手順（初回のみ・owner 操作）

1. [Zenn のダッシュボード → GitHubからのデプロイ](https://zenn.dev/dashboard/deploys) を開く
2. 「リポジトリを連携する」→ `TinMako/zenn-content` を選択して連携
3. 連携後、`articles/*.md` のうち `published: true` の記事が自動で公開される

連携が済めば、以降は「記事を書いて push」だけで公開・更新が回る（Web ログイン不要）。

## 記事一覧（現状）

| ファイル | published | 種別 |
|---|---|---|
| nagi-3000pct-impossible.md | true | idea |
| nagi-autonomous-fx-agent-design.md | true | tech |
| nagi-backtest-honest.md | true | tech |
| nagi-multiagent-llm-trading-anatomy.md | true | tech |
| nagi-zero-trades-three-layer-diagnosis.md | **false** | tech（owner 最終確認後に true へ） |
| vix-declining-automated-stoploss.md | true | tech |
| vix-low-strategy-backtest.md | true | tech |

## 注意

- `topics` は Zenn 側の仕様（半角英数字とハイフン推奨）。日本語トピックが公開時に弾かれた場合は英数字へ調整する。
- 記事の原本は `Nagi/articles/` にある。本リポジトリは公開用ミラー。
