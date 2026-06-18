# コンテスト概要：The Pokémon Company - PTCG AI Battle Challenge Simulation

URL: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle

## 目的

ポケモンカードゲーム（TCG）をプレイするAIエージェントを開発し、他チームのエージェントと対戦させてランキング上位を目指す。

確率・未知要素・戦略的計画が絡む環境でのAIエージェント訓練が主テーマ。

---

## タイムライン

| 日付 | イベント |
|------|---------|
| 2026年6月16日 | 開始日 |
| 2026年8月9日 | 参加登録・チーム合併締切 |
| 2026年8月16日 | 最終提出締切 |
| 2026年8月17日〜31日 | 最終評価期間（ゲーム継続） |

---

## ランキングシステム

- 各提出物はスキル評価 **N(μ, σ²)** でモデル化される
  - μ：推定スキル（初期値 600）
  - σ：不確実性（時間とともに減少）
- 勝利でμ上昇、敗北でμ低下、引き分けで平均に近づく
- 更新量は期待値からの偏差とσに比例

---

## エージェントの仕組み

バトルエンジン：**cabt Engine**（Kaggle環境向けポケモンTCGシミュレーター）

毎ターン、エージェントは以下を受け取る：
- ゲームログ
- 現在の盤面状態
- 合法的な選択肢のリスト

エージェントは **選んだ選択肢のインデックス（整数）** を返す。

APIドキュメント：https://matsuoinstitute.github.io/cabt/

---

## 提出形式

```
submission.tar.gz
├── main.py      # エージェントのメインファイル（トップディレクトリに配置）
└── deck.csv     # 使用するデッキ
```

作成コマンド：
```bash
tar -czvf submission.tar.gz *
```

- 1日最大5エージェントを提出可能
- 最新2提出のみが追跡される
- アップロード後、まず自身のコピーと対戦して動作確認される

---

## 賞品

- コンテスト自体に賞金なし
- ハッカソン部門にレポートを提出した参加者は賞品対象
  - 最終順位 = リーダーボード成績 + ハッカソン評価

---

## 参考リンク

- [APIドキュメント（cabt Engine）](https://matsuoinstitute.github.io/cabt/)
- [Kaggle Environments GitHub](https://github.com/Kaggle/kaggle-environments)
- [ポケモンTCGルールブック](https://www.pokemon-card.com/rules/)
