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
├── CLAUDE.md                   # このファイル
├── README.md                   # プロジェクト概要（UTF-16 LE）
├── docs/
│   ├── contest_overview.md     # コンテスト詳細（UTF-8）
│   ├── api_reference.md        # cabt Engine API仕様（UTF-8）
│   └── progress.md             # 進捗管理（UTF-8）
├── data/raw/
│   ├── EN_Card_Data.csv        # 英語カードデータ
│   ├── JP_Card_Data.csv        # 日本語カードデータ
│   ├── Card_ID List_EN.pdf     # カードIDリスト（英語）
│   └── Card_ID List_JP.pdf     # カードIDリスト（日本語）
├── sample_submission/          # サンプル（変更しない）
│   ├── main.py                 # ランダムエージェント（参照用）
│   ├── deck.csv                # サンプルデッキ
│   └── cg/                     # cabt Engine Python バインディング
├── submission/                 # 実際の提出物（ここを編集する）
│   ├── main.py                 # エージェント本体
│   ├── deck.csv                # 使用デッキ
│   └── cg/                     # cabt Engine Python バインディング
└── submission.tar.gz           # 提出用アーカイブ
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
search_begin(...)   # 探索状態を初期化
search_step(id, select)  # 1ステップ進める
search_end()        # 終了・メモリ解放
search_release(id)  # 特定IDを破棄
```

---

## 提出手順

```bash
cd submission
tar -czvf ../submission.tar.gz *
```

その後、`submission.tar.gz` を Kaggle にアップロード。

---

## 開発方針

1. **編集対象は `submission/` のみ**（`sample_submission/` は参照用として変更しない）
2. **`cg/` ディレクトリは変更しない**（バイナリの cabt Engine バインディング）
3. デッキは `submission/deck.csv` を編集（カードID 60行）
4. エージェントロジックは `submission/main.py` に実装

---

## 参考リンク

- [cabt Engine API ドキュメント](https://matsuoinstitute.github.io/cabt/)
- [Kaggle Environments GitHub](https://github.com/Kaggle/kaggle-environments)
- [ポケモンTCGルールブック](https://www.pokemon-card.com/rules/)
