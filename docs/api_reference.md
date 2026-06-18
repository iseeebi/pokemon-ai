# cabt Engine API リファレンス

公式ドキュメント: https://matsuoinstitute.github.io/cabt/

バージョン: 0.1.0

---

## モジュール構成

| モジュール | 役割 |
|-----------|------|
| `api` | 列挙型・データクラス・変換関数 |
| `game` | バトル制御（高レベル関数） |
| `sim` | C++バックエンドとのバインディング（低レベル） |
| `utils` | ユーティリティ関数 |

---

## エージェントの基本構造

毎ターン、エージェントは `obs_dict`（Observationの辞書）を受け取り、選んだ選択肢のインデックスのリストを返す。

```python
# main.py - 最小構成エージェント（ランダム選択）
import random

def agent(obs_dict: dict) -> list[int]:
    return random.sample(
        list(range(len(obs_dict["select"]["option"]))),
        obs_dict["select"]["maxCount"]
    )
```

### deck.csv

カードIDを1行1枚、計60枚。

```
1
1
2
3
...（合計60行）
```

---

## Observation（観測データ）

エージェントへの入力オブジェクト。

| フィールド | 型 | 説明 |
|-----------|---|------|
| `logs` | Log[] | 過去のアクションとゲームイベントの記録 |
| `current` | State or None | 現在のボード状態（デッキ選択段階では None） |
| `select` | SelectData or None | 利用可能な選択肢（デッキ選択段階では None） |
| `search_begin_input` | - | 初期デッキ選択時のみ使用 |

---

## State（ゲーム状態）

| フィールド | 型 | 説明 |
|-----------|---|------|
| `turn` | int | ターン数 |
| `turnActionCount` | int | 現ターンのアクション数 |
| `yourIndex` | int | 自分のプレイヤーインデックス |
| `firstPlayer` | int | 先手プレイヤーのインデックス |
| `supporterPlayed` | bool | サポーター使用済みか |
| `stadiumPlayed` | bool | スタジアム使用済みか |
| `energyAttached` | bool | エネルギー付け済みか |
| `retreated` | bool | 撤退済みか |
| `stadium` | Card or None | 現在のスタジアムカード |
| `players` | PlayerState[] | 各プレイヤーの状態（インデックス0,1） |
| `result` | int or None | ゲーム結果 |

---

## PlayerState（プレイヤー状態）

| フィールド | 型 | 説明 |
|-----------|---|------|
| `active` | Card or None | バトルポケモン（裏向きはNone） |
| `bench` | Card[] | ベンチポケモン（最大5枚） |
| `hand` | Card[] | 手札（自分のみ全表示、相手は枚数のみ） |
| `prize` | Card or None[] | サイドカード（裏向きはNone、最初が下・最後が上） |
| `discard` | Card[] | 捨て札 |
| `deckCount` | int | デッキ残数 |
| `handCount` | int | 手札枚数 |
| `benchMax` | int | ベンチ最大数（通常5） |
| `poisoned` | bool | 毒状態 |
| `burned` | bool | やけど状態 |
| `asleep` | bool | ねむり状態 |
| `paralyzed` | bool | まひ状態 |
| `confused` | bool | こんらん状態 |

---

## SelectData（選択データ）

| フィールド | 型 | 説明 |
|-----------|---|------|
| `type` | SelectType | 選択カテゴリー |
| `context` | SelectContext | 選択の詳細文脈 |
| `minCount` | int | 最小選択数 |
| `maxCount` | int | 最大選択数 |
| `option` | Option[] | 選択肢リスト |
| `deck` | - | デッキ情報 |
| `contextCard` | Card or None | 文脈カード |
| `effect` | - | 効果 |
| `remainDamageCounter` | int | 残ダメージカウンター |
| `remainEnergyCost` | - | 残エネルギーコスト |

---

## Option（選択肢）

| フィールド | 型 | 説明 |
|-----------|---|------|
| `type` | OptionType | 選択肢の種別 |
| `number` | int | 番号 |
| `area` | AreaType | カードの配置場所 |
| `index` | int | インデックス |
| `playerIndex` | int | プレイヤーインデックス |
| `toolIndex` | int | ツールインデックス |
| `energyIndex` | int | エネルギーインデックス |
| `inPlayArea` | AreaType | 場のエリア |
| `inPlayIndex` | int | 場のインデックス |
| `attackId` | int | 攻撃ID |
| `cardId` | int | カードID |
| `serial` | int | カードのユニークID |
| `specialConditionType` | SpecialConditionType | 特殊状態種別 |

---

## 列挙型

### AreaType（カードの配置場所）

| 値 | 名前 | 説明 |
|----|------|------|
| 1 | DECK | デッキ |
| 2 | HAND | 手札 |
| 3 | DISCARD | 捨て札 |
| 4 | ACTIVE | バトル場 |
| 5 | BENCH | ベンチ |
| 6 | PRIZE | サイド |
| 7 | STADIUM | スタジアム |
| 8 | ENERGY | エネルギー |
| 9 | TOOL | ポケモンのどうぐ |
| 10 | PRE_EVOLUTION | 進化前 |
| 11 | PLAYER | プレイヤー |
| 12 | LOOKING | 確認中 |

### EnergyType（エネルギータイプ）

| 値 | 名前 |
|----|------|
| 0 | COLORLESS |
| 1 | GRASS |
| 2 | FIRE |
| 3 | WATER |
| 4 | LIGHTNING |
| 5 | PSYCHIC |
| 6 | FIGHTING |
| 7 | DARKNESS |
| 8 | METAL |
| 9 | DRAGON |
| 10 | RAINBOW |
| 11 | TEAM_ROCKET |

### CardType（カード種別）

| 値 | 名前 |
|----|------|
| 0 | POKEMON |
| 1 | ITEM |
| 2 | TOOL |
| 3 | SUPPORTER |
| 4 | STADIUM |
| 5 | BASIC_ENERGY |
| 6 | SPECIAL_ENERGY |

### SelectType（選択カテゴリー）

| 値 | 名前 | 説明 |
|----|------|------|
| 0 | MAIN | 主要アクション |
| 1 | CARD | カード選択 |
| 2 | ATTACHED_CARD | 付いているカード選択 |
| 3 | ENERGY | エネルギー選択 |
| 4 | SKILL | 特性選択 |
| 5 | ATTACK | 攻撃選択 |
| 6 | EVOLVE | 進化選択 |
| 7 | COUNT | 数量選択 |
| 8 | YES_NO | はい/いいえ |
| 9 | SPECIAL_CONDITION | 特殊状態選択 |
| 10 | （予備） | - |

### OptionType（選択肢の種別）

| 値 | 名前 |
|----|------|
| 0 | NUMBER |
| 1 | YES |
| 2 | NO |
| 3 | CARD |
| 4 | TOOL_CARD |
| 5 | ENERGY_CARD |
| 6 | ENERGY |
| 7 | PLAY |
| 8 | ATTACH |
| 9 | EVOLVE |
| 10 | ABILITY |
| 11 | DISCARD |
| 12 | RETREAT |
| 13 | ATTACK |
| 14 | END |
| 15 | SKILL |
| 16 | SPECIAL_CONDITION |

### SpecialConditionType（特殊状態）

| 値 | 名前 |
|----|------|
| 0 | POISON |
| 1 | BURN |
| 2 | SLEEP |
| 3 | PARALYZE |
| 4 | CONFUSE |

### LogType（ゲームイベント）

SHUFFLE から RESULT まで、ゲーム中のすべてのアクションと状態変化を記録（0〜23）。

---

## CardData（カード定義）

`all_card_data()` で取得できる全カード情報。

| フィールド | 説明 |
|-----------|------|
| `name` | カード名 |
| `cardType` | CardType |
| `hp` | HP |
| `retreatCost` | 逃げるコスト |
| `weakness` | 弱点タイプ |
| `resistance` | 抵抗力タイプ |
| `energyType` | エネルギータイプ |
| `basic / stage1 / stage2` | 進化段階 |
| `ex / megaEx / tera / aceSpec` | 特殊フラグ |
| `evolvesFrom` | 進化前カード名 |
| `skills` | 特性リスト |
| `attacks` | 攻撃IDリスト |

## Attack（攻撃定義）

`all_attack()` で取得できる全攻撃情報。

| フィールド | 説明 |
|-----------|------|
| `attackId` | 攻撃ID |
| `name` | 攻撃名 |
| `damage` | ダメージ |
| `energies` | 必要エネルギーリスト |
| `text` | 攻撃テキスト |

---

## game モジュール関数

### `battle_start(deck0, deck1)`

2つのデッキでバトルを開始する。

```python
obs, start_data = battle_start(deck0, deck1)
# deck0, deck1: 各60枚のカードIDリスト
# 返り値: (Observation | None, StartData)
# 60枚でなければ ValueError
```

### `battle_select(select_list)`

プレイヤーの選択を適用して状態を1ステップ進める。

```python
obs = battle_select([0])  # インデックス0の選択肢を選ぶ
# 返り値: dict形式の新しいObservation
```

### `battle_finish()`

バトルを終了してメモリを解放する。

### `visualize_data()`

現在のボード状態を人間が読める形式で出力（デバッグ用）。

---

## sim モジュール（探索API）

### `search_begin(...)`

Observationに基づいて探索状態を初期化する。

### `search_step(search_id, select)`

指定された選択で探索状態を1ステップ進める。

### `search_end()`

現在の探索状態を終了してメモリを解放する。

### `search_release(search_id)`

特定の探索IDを明示的に破棄する。

---

## テストスクリプト例

```python
from kaggle_environments import make
from agent import agent

with open("deck.csv") as f:
    deck = [int(line) for line in f.readlines() if line.strip()]

env = make("cabt", configuration={"decks": [deck, deck]})
env.run([agent, agent])

# HTML形式で結果を保存
with open("result.html", "w") as f:
    f.write(env.render(mode="html"))
```

---

## 設計上の注意点

- エンジンは常に**合法手のみ**を `option` に提示する（不正な手を選ぶ必要はない）
- 相手の手札・デッキは非公開（**不完全情報ゲーム**）
- `current` と `select` はデッキ選択段階では `None` になる
- 公式のポケモンTCGルールとシミュレーターの動作には一部差異あり（[詳細はこちら](https://matsuoinstitute.github.io/cabt/)）
