---
title: "正直なバックテストの作り方——カーブフィッティングを排除する DSR・walk-forward 実践"
emoji: "🔬"
type: "tech"
topics: ["バックテスト", "統計", "Python", "数量ファイナンス", "個人開発"]
published: true
---

> **免責**: 本記事はバックテスト手法の技術解説です。投資助言・売買推奨ではありません。記載のコードはデモ口座・研究用途向けです。

バックテストで「年利 120%」が出た。しかし実際に運用したら「−15%」だった——そういう話は珍しくない。

この記事では、その乖離がなぜ起きるか数学的に説明し、**実装者が明日から使える 3 つの対策**（コスト控除・walk-forward・Deflated Sharpe Ratio）を Python コード付きで解説する。

---

## 1. バックテストが「嘘をつく」3 つの原因

### 1-1. カーブフィッティング（過剰最適化）

過去データに対して多数のパラメータを最適化すると、過去の「ノイズ」まで学習する。

```python
# NG: グリッドサーチで最良パラメータを探す
best_params = grid_search(data=in_sample, strategy=ma_cross, param_grid={
    "short": range(5, 50),
    "long": range(20, 200),
})
# → in-sample では最高 Sharpe だが、OOS では崩壊する
```

68 通りの戦略を試して「最良」を選べば、その最良は統計的な偶然を含む。

### 1-2. ルックアヘッドバイアス

未来の情報を過去に参照してしまう実装ミス。

```python
# NG: 終値でシグナル生成し同日終値で約定（実際は翌日始値）
signal = ma_cross(close_today)  
trade_at = close_today  # ← ルックアヘッド

# OK: 翌日始値で約定
signal = ma_cross(close_today)
trade_at = open_tomorrow
```

### 1-3. 取引コストの無視

スプレッド・スリッページ・手数料を無視すると、実戦で即座に収益が消える。

EURUSD の場合、典型的なスプレッドは 0.0001〜0.0002（1〜2 pips）。1 日 5 回転する戦略なら年間のコスト比率は大きく積み上がる。

---

## 2. 正直なバックテストに必要な 3 つの実装

### 2-1. 取引コスト控除

```python
COSTS = {
    "EURUSD": 0.00012,  # spread (half round-trip)
    "USDJPY": 0.011,
    "GBPUSD": 0.00015,
}

def apply_costs(returns: pd.Series, symbol: str, num_trades: int, n_bars: int) -> pd.Series:
    """1取引ごとのコストを returns から控除する。"""
    cost_per_bar = COSTS[symbol] * num_trades / n_bars
    return returns - cost_per_bar
```

### 2-2. Walk-Forward 検証

In-Sample（IS）で最適化 → Out-of-Sample（OOS）で検証 → 次の IS+OOS ウィンドウへ。

```python
def walk_forward(
    data: pd.DataFrame,
    strategy_fn,
    is_size: int = 252 * 3,   # 3年 in-sample
    oos_size: int = 252,       # 1年 out-of-sample
) -> pd.Series:
    """Walk-forward 検証でOOS returns を連結して返す。"""
    oos_results = []
    n = len(data)
    start = 0
    
    while start + is_size + oos_size <= n:
        is_data  = data.iloc[start : start + is_size]
        oos_data = data.iloc[start + is_size : start + is_size + oos_size]
        
        # IS で最適化
        best_params = strategy_fn.optimize(is_data)
        
        # OOS で評価（最適化なし）
        oos_returns = strategy_fn.backtest(oos_data, params=best_params)
        oos_results.append(oos_returns)
        
        start += oos_size  # 1ウィンドウ前進
    
    return pd.concat(oos_results)
```

OOS returns だけを連結することで、過去に見ていないデータでの実力を測れる。

### 2-3. Deflated Sharpe Ratio（DSR）— 多重検定補正

単一戦略の Sharpe Ratio は「この戦略は偶然よりも有意か」を問わない。複数の戦略を試せば、偶然に高い Sharpe が出る確率は増大する。

DSR はこの**試行数の膨らみを補正**した Sharpe Ratio だ。

```python
from scipy.stats import norm
import numpy as np

def deflated_sharpe_ratio(
    sr_hat: float,          # OOS Sharpe Ratio（実測）
    sr_benchmark: float,    # ベンチマーク（通常 0）
    n_trials: int,          # 試行した戦略の数
    n_obs: int,             # OOS 期間のサンプル数（日数等）
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """
    Bailey & Lopez de Prado (2014) の DSR。
    返り値: DSR（0〜1）。0.95 以上を有意の目安とする。
    """
    e_max_sr = (
        (1 - np.euler_gamma) * norm.ppf(1 - 1 / n_trials)
        + np.euler_gamma * norm.ppf(1 - 1 / (n_trials * np.e))
    )
    v = (
        (1 - skew * sr_hat + (kurtosis - 1) / 4 * sr_hat**2)
        / (n_obs - 1)
    ) ** 0.5
    z = (sr_hat - e_max_sr) / v
    return float(norm.cdf(z))
```

**使い方**:

```python
oos_sr   = compute_sharpe(oos_returns)
n_trials = 68                           # 試した戦略数
n_obs    = len(oos_returns)

dsr = deflated_sharpe_ratio(oos_sr, 0, n_trials, n_obs)
print(f"DSR = {dsr:.3f}")
# 0.95 以上 → 有意 / 0.95 未満 → 採用しない
```

---

## 3. 実際のデータで試した結果

Nagi 開発の過程で、12銘柄 × 68戦略をこの手順でバックテストした。

| ステップ | IS Sharpe 最良 | OOS Sharpe | DSR |
|:--|--:|--:|--:|
| コスト無視・IS最適化のみ | **2.14** | — | — |
| コスト控除・IS最適化 | 1.47 | — | — |
| + walk-forward OOS | — | 0.82 | — |
| + DSR（N=68補正後） | — | — | **0.81** |

DSR 0.95 未満 → **統計的に有意でない**。IS で良く見えた戦略のどれも、実戦で再現する保証がない。

### コスト無視が引き起こす「幻の高リターン」

USDJPY の最良戦略を例に：

```
コスト無視: CAGR +34.2% / Sharpe 1.47
コスト控除: CAGR  +8.1% / Sharpe 0.62  ← 実態
```

コストだけで CAGR が 26% 消えた。

---

## 4. 自分のバックテストを診断するチェックリスト

```
□ 終値シグナル → 翌日始値約定になっているか（ルックアヘッド排除）
□ スプレッド・スリッページ・手数料を控除しているか
□ IS と OOS を完全に分けているか
□ walk-forward 検証を実施しているか
□ 試行した戦略数 N を記録してあるか（DSR 計算に必須）
□ DSR を計算したか。0.95 以上か？
□ IS Sharpe と OOS Sharpe の乖離を確認したか
```

このリストが全部 ✅ のバックテストだけを「正直なバックテスト」と呼んでよい。

---

## 5. まとめ

| 手法 | 何を防ぐか |
|:--|:--|
| コスト控除 | 「実戦で即死」する幻の好成績 |
| Walk-Forward | IS 最適化の過学習 |
| Deflated Sharpe Ratio | 多重検定による偶然の最良選出 |

Nagi の最良戦略も、この基準を全て通して DSR < 0.95 だった。それが今の正直な現在地だ。

---

## 参考

- Bailey, D. H., & Lopez de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality*. Journal of Portfolio Management.
- 実装コード: [challenge-3000pct リポジトリ](https://github.com/TinMako/challenge-3000pct)（harness.py に DSR・walk-forward・コスト控除を実装済み）

---

*このシリーズ: [記事01: Nagiシステム解剖](https://zenn.dev/tinmako/articles/nagi-autonomous-trading) | [記事02: 年3000%の数学](https://zenn.dev/tinmako/articles/nagi-3000pct-impossible) | 記事03: 正直なバックテスト（本記事）*
