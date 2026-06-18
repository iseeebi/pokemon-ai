# ルールベースエージェント 実装リファレンス

4つのサンプルデッキ（Iono's Voltorb / Mega Lucario ex / Mega Abomasnow ex / Dragapult ex）から抽出した共通パターン・実装テクニックのまとめ。

---

## 1. エージェントの基本骨格

```python
import os
from collections import defaultdict
from cg.api import (
    AreaType, CardType, EnergyType,
    Observation, SelectContext, OptionType,
    Card, Pokemon, all_card_data, to_observation_class
)

# カードデータの初期化（起動時に一度だけ）
all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}

# デッキ読み込み
file_path = "deck.csv"
if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
with open(file_path, "r") as f:
    csv = f.read().split("\n")
my_deck = [int(csv[i]) for i in range(60)]

def agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)

    # デッキ選択フェーズ（select が None）
    if obs.select is None:
        return my_deck

    state   = obs.current
    select  = obs.select
    context = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]

    # --- 盤面情報の集計 ---
    # （後述の「盤面集計パターン」を参照）

    # --- 各選択肢のスコアリング ---
    scores = []
    for o in select.option:
        score = 0
        # （後述の「OptionType 別スコアリング」を参照）
        scores.append(score)

    # スコア降順でインデックスを返す
    desc_indices = [i for i, _ in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)]
    return desc_indices[:select.maxCount]
```

---

## 2. 共通ヘルパー関数

### get_card — 任意ゾーンからカードを取得

```python
def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> Pokemon | Card | None:
    ps = obs.current.players[player_index]
    match area:
        case AreaType.DECK:    return obs.select.deck[index]
        case AreaType.HAND:    return ps.hand[index]
        case AreaType.DISCARD: return ps.discard[index]
        case AreaType.ACTIVE:  return ps.active[index]
        case AreaType.BENCH:   return ps.bench[index]
        case AreaType.PRIZE:   return ps.prize[index]
        case AreaType.STADIUM: return obs.current.stadium[index]
        case AreaType.LOOKING: return obs.current.looking[index]
        case _:                return None
```

### prize_count — KO 時のサイド獲得枚数

```python
def prize_count(pokemon: Pokemon) -> int:
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:   # Legacy Energy（サイド−1）
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:  # Lillie's Pearl
            count -= 1
    return max(0, count)
```

### pokemon_score — 相手ポケモンの攻撃ターゲットとしての価値

```python
def pokemon_score(pokemon: Pokemon, is_attack_damage: bool) -> int:
    data = card_table[pokemon.id]
    score = prize_count(pokemon) * 1000   # サイド枚数が最重要
    score += len(pokemon.energies) * 150  # エネルギー損失を評価
    score += len(pokemon.tools) * 100
    if data.stage2: score += 250
    elif data.stage1: score += 130
    score += pokemon.hp
    return score
```

---

## 3. 盤面集計パターン

```python
field_counts   = defaultdict(int)  # 場（バトル場+ベンチ）のカードID別枚数
hand_counts    = defaultdict(int)  # 手札のカードID別枚数
discard_counts = defaultdict(int)  # 捨て札のカードID別枚数

for card in my_state.active + my_state.bench:
    if card is None:
        continue
    field_counts[card.id] += 1
    # エネルギー数チェックなどデッキ固有の集計はここで

for card in my_state.hand:
    hand_counts[card.id] += 1

for card in my_state.discard:
    discard_counts[card.id] += 1

# スタジアムID
stadium_id = 0
for card in state.stadium:
    stadium_id = card.id
```

---

## 4. OptionType 別スコアリング

スコアの大小で優先度を表現する。**負のスコア（-1 など）はその行動を選ばないことを意味する**。

### NUMBER / YES

```python
elif o.type == OptionType.NUMBER:
    score = o.number          # ドロー枚数など → 多い方を優先

elif o.type == OptionType.YES:
    score = 1                 # 基本は「はい」を優先
```

### PLAY（カードをプレイ）

```python
elif o.type == OptionType.PLAY:
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]

    if data.cardType == CardType.POKEMON:
        score = 100000        # ポケモンを場に出すのは最優先
        # 条件により -1（例：ベンチが不要な場合）

    elif data.cardType == CardType.SUPPORTER:
        score = 25000         # サポーターは高優先
        # 既にサポーターを使った or デッキが少ない場合は -1

    elif data.cardType == CardType.STADIUM:
        score = 85000         # スタジアム
        # 同名スタジアムが既に出ている場合は -1

    else:  # ITEM / TOOL
        # カード固有の条件でスコア設定
        # 例：Night Stretcher は捨て札に欲しいカードがある場合のみ
        score = ...
```

### EVOLVE（進化）

```python
elif o.type == OptionType.EVOLVE:
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    score = 110000 + len(pokemon.energies)  # 進化は最最優先（エネルギーが多いほど高）
    # ただし不要な場合（ex 枚数制限など）は -1
```

### ATTACH（エネルギー/どうぐを付ける）

```python
elif o.type == OptionType.ATTACH:
    card    = get_card(obs, o.area, o.index, my_index)
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)

    # どうぐ
    if card_table[card.id].cardType == CardType.TOOL:
        score = 60000
        if o.inPlayArea == AreaType.ACTIVE:
            score += 1000

    # エネルギー：付けるポケモンと現在のエネルギー量で細かく調整
    else:
        energy_count = len(pokemon.energies)
        score = 8000
        if pokemon.id == MAIN_ATTACKER_ID:
            if energy_count < REQUIRED_ENERGY:
                score += 1000    # まだ必要なら加点
        if o.inPlayArea == AreaType.ACTIVE:
            score += 10          # バトル場は少し優先
```

### ABILITY（特性）

```python
elif o.type == OptionType.ABILITY:
    card = get_card(obs, o.area, o.index, my_index)
    score = 30000                # 基本は高優先
    # 特定の特性は条件付き
    # 例：ドロー系 → デッキ残り少ない場合は -1
    if my_state.deckCount <= 5:
        score = -1
```

### RETREAT（にげる）

```python
elif o.type == OptionType.RETREAT:
    # 攻撃準備ができたポケモンがベンチにいる場合のみ有効
    if bench_attacker and not active_attacker:
        score = 10000
    else:
        score = -1
```

### ATTACK（攻撃）

```python
elif o.type == OptionType.ATTACK:
    score = o.attackId           # デフォルトは攻撃IDをスコアに
    # または固定値で攻撃を最後に実行させる（ターン最後の行動）
    score = 1000
    # 特定の攻撃IDを優先
    if o.attackId == TARGET_ATTACK_ID:
        score += 100
```

### CARD（カード選択）

`SelectContext` によって意味が変わる。

```python
elif o.type == OptionType.CARD:
    card = get_card(obs, o.area, o.index, o.playerIndex)
    if card is None:
        scores.append(0)
        continue

    if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE, SelectContext.SETUP_ACTIVE_POKEMON):
        # バトル場に出すポケモンを選ぶ
        score += len(card.energies) * 100   # エネルギーが多いほど優先
        if card.id == MAIN_ATTACKER_ID:
            score += 5000
        if card.id == TANKER_ID:
            score += 1000

    elif context in (SelectContext.TO_BENCH, SelectContext.TO_HAND):
        # ベンチや手札に加えるカードを選ぶ
        # 場に不足しているポケモンを優先
        if card.id == NEEDED_POKEMON_ID and field_counts[card.id] == 0:
            score += 5000
        # 重複は減点
        if hand_counts[card.id] >= 1:
            score -= 2000

    elif context == SelectContext.DISCARD:
        # 捨てるカードを選ぶ → 不要なカードを高スコアに
        score = -hand_scores[o.index]   # 手札スコアの逆転
        if card.id == BASIC_ENERGY_ID:
            score += 100   # エネルギーは捨てやすい
        if hand_counts[card.id] >= 2:
            score += 500   # 重複カードを優先して捨てる

    elif context == SelectContext.DAMAGE_COUNTER:
        # ダメカン配布先を選ぶ（Dragapult ex 等）
        score = 100000 - 10 * card.hp + pokemon_score(card, False)
        if 40 <= card.hp <= 90:
            score += 10000   # 低HP ポケモンへのKO狙い

    elif context == SelectContext.ATTACH_FROM:
        # 付け先を選ぶ（エネルギー加速効果など）
        score = energy_score(card, o.area == AreaType.ACTIVE)
```

---

## 5. グローバル状態管理（ターン跨ぎの情報保持）

ターンをまたいで情報を持ち越す必要がある場合は global 変数を使用。

```python
pre_turn  = 0
plan      = AttackPlan()   # 攻撃計画（アタッカー・ターゲット）
ability_used = False       # その特性がそのターンに使われたか

def agent(obs_dict: dict) -> list[int]:
    global pre_turn, plan, ability_used

    # ターンが変わったらリセット
    if pre_turn != state.turn:
        pre_turn = state.turn
        plan = AttackPlan()
        ability_used = False
```

### AttackPlan パターン（Mega Lucario ex / Dragapult ex より）

```python
class AttackPlan:
    attacker: int = -1   # 使うアタッカーのインデックス（0=バトル場, 1〜=ベンチ）
    target:   int = -1   # 狙う相手のインデックス（0=バトル場, 1〜=ベンチ）
    attack_index: int = -1  # 攻撃インデックス
    remain_hp: int = -1     # 攻撃後の相手残りHP（KO判定に使用）
    energy: bool = False    # エネルギーを付ける必要があるか
```

MAIN フェーズで全アタッカー×全ターゲットの組み合わせを事前評価し、最良プランを保持する。

---

## 6. 攻撃プランニング（Lucario / Dragapult パターン）

```python
if context == SelectContext.MAIN:
    # 弱点・抵抗力を考慮したダメージ計算
    damage = base_damage
    op_data = card_table[op_pokemon.id]
    if op_data.weakness == EnergyType.FIGHTING:
        damage *= 2
    elif op_data.resistance == EnergyType.FIGHTING:
        damage -= 30

    # KO 判定
    if op_pokemon.hp <= damage:
        prize = prize_count(op_pokemon)
        # 残りサイドを取り切れるなら最優先
        if len(op_state.prize) <= prize:
            score = 50000
```

---

## 7. デッキ残量チェック（山切れ防止）

```python
no_draw = (my_state.deckCount <= 5)   # 残り5枚以下でドロー系を抑制

# ドロー系カードのスコアリングで使用
elif card.id == DRAW_SUPPORTER_ID:
    if no_draw:
        score = -1
    else:
        score = 25000
```

---

## 8. スコア設計の目安（優先度の大小感）

| 優先度 | スコード範囲 | 代表的な行動 |
|--------|------------|------------|
| 最高   | 100000〜   | 進化、ゲームに勝てる攻撃 |
| 高     | 50000〜99999 | ポケモンを出す、KOを取れる行動 |
| 中高   | 20000〜49999 | 主要トレーナーをプレイ、アタッカー準備 |
| 中     | 5000〜19999  | サポーター、撤退、エネルギー加速 |
| 低     | 1000〜4999   | アイテム、エネルギー付け |
| 最低   | 0〜999       | 攻撃（ターン最後に実行させる） |
| 禁止   | -1（負値）   | その行動を選ばない |

---

## 9. サンプルデッキ別 特徴まとめ

### Iono's Voltorb（中級）
- **戦術**: Bellibolt ex の特性でエネルギーを大量付与 → Voltorb が高ダメージ
- **実装の特徴**:
  - `can_attack` フラグをターン内で管理（攻撃可能になったら不要なエネルギー付けを抑制）
  - 手札スコア（`hand_scores`）を事前計算し、捨て選択時に逆転利用
  - `unused_hand_count` で不要手札枚数を管理（Ultra Ball 発動条件に使用）

### Mega Lucario ex（中級）
- **戦術**: 複数アタッカー（Lucario ex・Hariyama・Solrock）を状況で切り替え
- **実装の特徴**:
  - `AttackPlan` による事前攻撃計画（ターン開始時に全組み合わせを評価）
  - `prize_count()` / `pokemon_score()` ヘルパーで汎用的なターゲット評価
  - Boss Orders でのベンチ呼び出し判定を `plan.target >= 1` で制御

### Mega Abomasnow ex（初級・シンプル）
- **戦術**: 水エネルギー34枚 + Hammer-lanche（捨てた水エネ × 100ダメ）
- **実装の特徴**:
  - `bench_attacker_index0/1` でアタッカーが既にいるかを管理
  - `switch_index` で次に出すポケモンを事前決定
  - コードが最もシンプル → 初めて書く際の参考に最適

### Dragapult ex（上級）
- **戦術**: Phantom Dive でベンチへのダメカン配布 → マルチKO
- **実装の特徴**:
  - `LogType` でログを解析し、前ターンのKO有無・相手のアイテム使用を検出
  - デッキ残枚数推定（`deck_counts`）でサイドカードの内容を推定
  - `plan_a/plan_b` の二段階計画（ボスあり・なし）
  - ダメカン配布先の組み合わせ探索（KO できる組み合わせを全列挙）
  - `no_damage_dex()` / `no_damage_counter()` で免疫持ちポケモンを除外
