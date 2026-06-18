# CLAUDE.md — Pokemon AI Challenge ガイド

## プロジェクト概要

Kaggle コンテスト「The Pokémon Company - PTCG AI Battle Challenge Simulation」への参加プロジェクト。
ポケモンTCGをプレイするAIエージェントを開発する。

- コンテストURL: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle
- 締切: 2026年8月16日
- 進捗: `docs/progress.md` を参照

---

## ファイル構成

```
pokemon-ai/
├── CLAUDE.md                        # このファイル
├── README.md                        # プロジェクト概要（UTF-16 LE）
├── simulate.py                      # ローカル対戦シミュレーター（全デッキ共通）
├── opponents/                       # サンプル対戦相手エージェント4種（全デッキ共通）
│   ├── dragapult_ex.py
│   ├── iono.py
│   ├── mega_abomasnow.py
│   └── mega_lucario.py
├── agents/                          # デッキ×エージェントの開発ワークスペース
│   └── festival_lead/               # Festival Lead デッキ（現行）
│       ├── main.py                  # 現在開発中のエージェント本体
│       ├── deck.csv                 # デッキリスト
│       ├── InSampleList.txt         # 使用可能カードID一覧
│       ├── submit.py                # 提出スクリプト（圧縮・アーカイブ）
│       ├── results.json             # 各バージョンの勝率履歴（自動更新）
│       └── v{n}_agent.py            # 提出済みバージョンのアーカイブ（比較用）
│   └── (新デッキ名)/                # 新デッキはここに追加
│       ├── main.py
│       ├── deck.csv
│       └── submit.py
├── submission/                      # 提出スロット（submit.py が自動更新）
│   ├── main.py                      # エージェント本体
│   ├── deck.csv                     # 使用デッキ
│   └── cg/                          # cabt Engine Python バインディング（変更しない）
├── submissions/                     # 提出アーカイブ履歴
│   └── v{n}_{deck_name}.tar.gz
├── docs/
│   ├── contest_overview.md          # コンテスト詳細（UTF-8）
│   ├── api_reference.md             # cabt Engine API仕様（UTF-8）
│   └── progress.md                  # 進捗管理（UTF-8）
├── data/raw/
│   ├── EN_Card_Data.csv             # 英語カードデータ
│   ├── JP_Card_Data.csv             # 日本語カードデータ
│   ├── Card_ID List_EN.pdf          # カードIDリスト（英語）
│   └── Card_ID List_JP.pdf          # カードIDリスト（日本語）
├── notebooks/                       # 参照ノートブック（Kaggle公開サンプル）
└── sample_submission/               # 公式サンプル（変更しない）
    ├── main.py                      # ランダムエージェント（参照用）
    ├── deck.csv
    └── cg/                          # cabt Engine Python バインディング
```

---

## ファイルエンコーディング

- `README.md`: **UTF-16 LE**（PowerShellで `-Encoding Unicode` を使用）
- `docs/*.md` / `submission/*.py`: **UTF-8**（`[System.IO.File]::ReadAllText(..., UTF8)` を使用）

PowerShellでUTF-8ファイルを読む場合:
```powershell
[System.IO.File]::ReadAllText("path\to\file.md", [System.Text.Encoding]::UTF8)
```

---

## エージェントの仕組み

### インターフェース（`submission/main.py`）

```python
def agent(obs_dict: dict) -> list[int]:
    # obs.select が None のとき: デッキ選択フェーズ → カードID 60枚のリストを返す
    # それ以外: obs.select.option のインデックスリストを返す
    #   - 長さは minCount 以上 maxCount 以下
    #   - 重複不可、各値は 0 以上 len(option) 未満
```

### ゲーム状態（主要フィールド）

| オブジェクト | 説明 |
|---|---|
| `obs.logs` | 過去のゲームイベント記録 |
| `obs.current` | 現在のボード状態（`State`） |
| `obs.select` | 現在の選択肢（`SelectData`） |
| `state.players[i]` | プレイヤーiの状態（`PlayerState`） |
| `state.players[i].active` | バトル場のポケモン |
| `state.players[i].bench` | ベンチ（最大5枚） |
| `state.yourIndex` | 自分のプレイヤーインデックス |

### 探索API（`cg.sim`）

```python
search_begin(...)        # 探索状態を初期化
search_step(id, select)  # 1ステップ進める
search_end()             # 終了・メモリ解放
search_release(id)       # 特定IDを破棄
```

---

## 開発フロー

### 1. エージェントを改良する

`agents/{deck_name}/main.py` を編集する。

### 2. ローカルで評価する

プロジェクトルートから `simulate.py` を実行する。

```bash
# 現在の main.py を4種の対戦相手と対戦させる（デフォルト: 100試合×4）
python simulate.py festival_lead

# 試合数を減らしてクイックチェック（キャッシュを汚さない）
python simulate.py festival_lead --games 20

# 直近の提出済みバージョン vs current を比較（古いverは参考値表示）
python simulate.py festival_lead --compare
```

`--compare` の表示イメージ：

```
[festival_lead] Simulating: v2 vs current  (100 games each)
Reference (cached): v1

Version       Dragapult   Iono's Dec  Mega Aboma  Mega Lucar   TOTAL
--------------------------------------------------------------------
v1 *               9.0%       25.0%       26.0%       52.0%   28.0%  ← キャッシュ参照
v2                13.0%       35.0%       39.0%       58.0%   36.2%  ← シミュレート
current           20.0%       52.0%       34.0%       61.0%   41.8%  ← シミュレート
--------------------------------------------------------------------
* cached result
```

- シミュレートするのは「直近の提出済みバージョン」と「current」の2つのみ
- それより古いバージョンは `results.json` からキャッシュ参照（再シミュレートなし）
- `--games 50` 以上のときのみ named version の結果を `results.json` に保存

### 3. 提出する

`agents/{deck_name}/submit.py` を実行する。

```bash
cd agents/festival_lead
python submit.py
```

実行内容：
1. `main.py` を `v{n}_agent.py` としてアーカイブ（次回 `--compare` 用）
2. `submission/main.py` と `submission/deck.csv` を更新
3. `submissions/v{n}_{deck_name}.tar.gz` を作成
4. プロジェクトルートに `submission.tar.gz` を出力 → Kaggle にアップロード

### 4. 新デッキを追加する場合

```
agents/{新デッキ名}/
├── main.py
├── deck.csv
└── submit.py   # festival_lead/submit.py をコピーして deck 名部分を修正
```

`simulate.py` と `opponents/` はそのまま使えるため変更不要。

---

## エージェント設計方針

### ニーズベースアーキテクチャ

`agents/festival_lead/main.py` が採用している設計。カード取得・プレイのスコアリングを `needs` から一元的に導出する。

```python
needs: dict[int, int] = {}   # card_id → priority (1〜10)

def need(card_id: int, priority: int) -> None:
    if priority > needs.get(card_id, 0):
        needs[card_id] = priority

# 例: Thwackey コンボが発動できる状況なら最優先
if can_thwackey_combo:
    need(Thwackey, 10)

# サーチカードのスコアは needs から導出
score = needs.get(card.id, 0) * 100
```

優先度の目安: 10=今すぐ必要 / 7〜9=重要 / 4〜6=あると便利 / 1〜3=余裕があれば

---

## 不変ルール

- **`submission/cg/` と `sample_submission/` は変更しない**（バイナリの cabt Engine バインディング）
- **`submission/` の内容は `submit.py` 経由でのみ更新する**（直接編集しない）

---

## 参考リンク

- [cabt Engine API ドキュメント](https://matsuoinstitute.github.io/cabt/)
- [Kaggle Environments GitHub](https://github.com/Kaggle/kaggle-environments)
- [ポケモンTCGルールブック](https://www.pokemon-card.com/rules/)
