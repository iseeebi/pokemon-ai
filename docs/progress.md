# プロジェクト進捗

## 現状サマリー
- **フェーズ**: v1 ルールベースエージェント提出済み・改良中
- **提出物**: `submissions/v1_festival_lead.tar.gz`（Festival Lead デッキ）
- **締切**: 2026年8月16日

---

## 完了済み

### 環境・調査
- [x] Kaggle コンテスト把握（PTCG AI Battle Challenge Simulation）
- [x] cabt Engine API 仕様確認（`docs/api_reference.md`）
- [x] サンプル提出物の構成確認（`sample_submission/`）
- [x] カードデータ取得（`data/raw/EN_Card_Data.csv`, `JP_Card_Data.csv`）
- [x] ルールベースサンプル 4 本ダウンロード・分析（`notebooks/`）
- [x] RL + MCTS サンプルダウンロード（`notebooks/`）
- [x] 実装リファレンス作成（`docs/rule_based_agent_reference.md`）

### デッキ構築
- [x] Festival Lead デッキ設計（コンセプト: Festival Grounds + Festival Lead 特性で2回攻撃）
- [x] `newdeck/deck.csv` 作成・カードID 修正（InSampleList.txt 準拠）
- [x] `submission/deck.csv` へ反映

### エージェント実装（v1）
- [x] `newdeck/main.py` — Festival Lead デッキ用ルールベースエージェント
- [x] `submission/main.py` へ反映
- [x] `submissions/v1_festival_lead.tar.gz` 作成・Kaggle アップロード確認（エラーなし）

### v1 → v2 改良（2026-06-18）
リプレイ確認後に発見した問題を修正済み（`newdeck/main.py`、未提出）：

| 問題 | 修正内容 |
|------|----------|
| サーチ系カードの取得優先度が不適切 | Applin > Dipplin > Grookey > Thwackey > その他 に変更 |
| アタッカー以外が前に出やすい | 退場条件を「ベンチの Festival Lead にエネルギー不問」に緩和 |
| 倒された後 Thwackey が前に出る | 交代優先度でThwackey をGrookey/Applin より低く設定 |
| 前のアタッカーにエネルギーを2枚貼る | バトル場は1枚、Thwackey のみ2枚（逃げ用）に制限 |
| Applin にエネルギーを貼らない | Applin ベンチへの1枚付与を追加（進化後即攻撃対応） |

---

## 未着手・TODO

### エージェント改良
- [ ] 改良版を `submission/` へ反映・v2 提出
- [ ] 手動プレイのログを受け取り分析（ユーザーが別途送付予定）
- [ ] サポーター選択ロジックの精査
- [ ] Boss's Orders の対象選択ロジック
- [ ] Festival Lead 2回攻撃の最適化

### 発展
- [ ] MCTS（モンテカルロ木探索）の実装検討
- [ ] 強化学習の検討（sim モジュールの探索 API を活用）
- [ ] ローカルでの自己対戦テスト環境構築

---

## タイムライン（目安）

| 期間 | 目標 |
|------|------|
| 〜6月末 | リプレイログ分析・v2 改良版提出 |
| 〜7月中旬 | サポーター・コンボロジック強化 |
| 〜8月上旬 | 探索・評価関数の強化 |
| 8月16日 | 最終提出 |

---

## メモ

- `sim` モジュールの `search_begin` / `search_step` / `search_end` で探索ロールアウト可能
- 相手の手札・デッキは非公開（不完全情報ゲーム）
- ランキングはμ（初期値600）の大小で決定
- 1日最大5提出、最新2提出のみ追跡される
- 提出アーカイブは `submissions/` に `v{n}_xxx.tar.gz` 形式で保存
