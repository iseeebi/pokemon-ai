# プロジェクト進捗

## 現状サマリー
- **フェーズ**: v3 提出済み・次バージョン改良検討中
- **提出物**: `submissions/v3_festival_lead.tar.gz`（最新提出）
- **締切**: 2026年8月16日

---

## バージョン履歴と評価結果

| Version | Dragapult ex | Iono's Deck | Mega Abomasnow | Mega Lucario ex | TOTAL | 主な変更 |
|---------|-------------|-------------|----------------|-----------------|-------|---------|
| v1 | 9% | 25% | 26% | 52% | **28%** | 初版ルールベース |
| v2 | 13% | 35% | 39% | 58% | **36%** | Thwackey コンボ優先・Boss 条件修正・退場条件改善 |
| v3 | 27% | 58% | 40% | 54% | **45%** | ニーズベース + 人間フィードバックによる意思決定ルール精査・提出済み |

※各100試合、4種のサンプルルールベースエージェント相手の勝率

---

## 完了済み

### 環境・調査
- [x] Kaggle コンテスト把握（PTCG AI Battle Challenge Simulation）
- [x] cabt Engine API 仕様確認（`docs/api_reference.md`）
- [x] サンプル提出物の構成確認（`sample_submission/`）
- [x] カードデータ取得（`data/raw/EN_Card_Data.csv`, `JP_Card_Data.csv`）
- [x] ルールベースサンプル 4 本ダウンロード・分析（`notebooks/`）
- [x] RL + MCTS サンプルダウンロード（`notebooks/`）

### デッキ構築
- [x] Festival Lead デッキ設計（コンセプト: Festival Grounds + 特性で2回攻撃）
- [x] `agents/festival_lead/deck.csv` 作成・カードID 修正（InSampleList.txt 準拠）

### エージェント実装
- [x] **v1**: 初版ルールベースエージェント（`submissions/v1_festival_lead.tar.gz`）
- [x] **v2**: Thwackey コンボ優先・Boss 条件修正・エネルギー付与改善（`submissions/v2_festival_lead.tar.gz`）
- [x] **v3**: ニーズベース + 人間フィードバックによる意思決定ルール精査（`submissions/v3_festival_lead.tar.gz`）
  - `needs: dict[card_id, priority]` で必要カードを一元管理
  - 人間フィードバックでルール精査（Black Belt / Boss Orders / 進化優先度 / サポーター条件 / 捨て札判断 など）
  - Rabsca アビリティ: パッシブ保護、EX 相手で優先度アップ

### 開発インフラ
- [x] ローカルシミュレーター構築（`simulate.py` + `opponents/`）
  - cabt Engine を直接使用してKaggle提出なしで評価可能
  - 対戦相手: Dragapult ex / Iono's Deck / Mega Abomasnow / Mega Lucario ex
- [x] バージョン比較機能（`python simulate.py festival_lead --compare`）
  - 直近アーカイブ vs current のみシミュレート（2バージョン分）
  - 古いバージョンは `results.json` からキャッシュ参照（再シミュレートなし）
  - 50試合未満のクイックテストはキャッシュを上書きしない
- [x] 提出スクリプト（`agents/festival_lead/submit.py`）
  - 提出時に `v{n}_agent.py` を自動アーカイブ（次回比較用）
  - `submission/` 同期・tar.gz 作成を一括実行

---

## 未着手・TODO

### エージェント改良
- [ ] Dragapult ex 対策（v3 時点: 27%、最も勝率が低い）
- [ ] Mega Lucario ex 対策（v2→v3 で 58%→54% と微減）
- [ ] Mega Abomasnow 対策（v3 時点: 40%）
- [ ] Shaymin の活用方法検討

### 発展
- [ ] MCTS（モンテカルロ木探索）の実装検討
- [ ] 強化学習の検討（`cg.sim` の探索 API を活用）

---

## タイムライン（目安）

| 期間 | 目標 |
|------|------|
| 〜6月末 | v3 提出済み ✓ |
| 〜7月中旬 | Dragapult 対策・v4 改良版提出 |
| 〜8月上旬 | 探索・評価関数の強化 |
| 8月16日 | 最終提出 |

---

## メモ

- `sim` モジュールの `search_begin` / `search_step` / `search_end` で探索ロールアウト可能
- 相手の手札・デッキは非公開（不完全情報ゲーム）
- ランキングはμ（初期値600）の大小で決定
- 1日最大5提出、最新2提出のみ追跡される