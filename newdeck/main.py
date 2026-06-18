import os
import random
from collections import defaultdict

from cg.api import (
    AreaType, CardType, Observation, SelectContext, OptionType,
    Card, Pokemon, all_card_data, to_observation_class,
)

"""
Festival Lead Deck
Core combo: Festival Grounds + Dipplin/Goldeen/Seaking (Festival Lead) → attack twice per turn
Support: Thwackey (Boom Boom Groove: search any card when Festival Lead is active)
"""

file_path = "deck.csv"
if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
with open(file_path, "r", encoding="utf-8-sig") as f:
    my_deck = [int(line.strip()) for line in f if line.strip()]
if len(my_deck) != 60:
    raise ValueError(f"Deck size invalid: {len(my_deck)}")

all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}

# Decklist
Grookey          = 89    # ×4
Thwackey         = 90    # ×4
Applin_TWM       = 92    # ×3
Applin_SCR       = 149   # ×1
Dipplin          = 93    # ×4
Goldeen          = 100   # ×2
Seaking          = 240   # ×1
Rellor           = 73    # ×1
Rabsca           = 74    # ×1
Shaymin          = 343   # ×1
Lillie_Det       = 1227  # ×4
Black_Belt       = 1211  # ×2
Boss_Orders      = 1182  # ×2
Lana_Aid         = 1184  # ×1
Dawn             = 1231  # ×1
Kieran           = 1191  # ×1
Buddy_Poffin     = 1086  # ×4
Poke_Pad         = 1152  # ×4
Bug_Catching     = 1094  # ×4
Switch_Card      = 1123  # ×1
Night_Stretcher  = 1097  # ×1
Secret_Box       = 1092  # ×1
Air_Balloon      = 1174  # ×2
Brave_Bangle     = 1175  # ×2
Festival_Grounds = 1245  # ×4
Grass_Energy     = 1     # ×4

FESTIVAL_LEAD_IDS = {Dipplin, Goldeen, Seaking}


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


def agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return my_deck

    state    = obs.current
    select   = obs.select
    context  = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]

    # --- 盤面集計 ---
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)

    active_has_festival_lead = False
    festival_lead_on_bench   = False  # エネルギー不問（入れ替え判断用）

    for card in my_state.active:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id in FESTIVAL_LEAD_IDS:
            active_has_festival_lead = True

    for card in my_state.bench:
        field_counts[card.id] += 1
        if card.id in FESTIVAL_LEAD_IDS:
            festival_lead_on_bench = True

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    stadium_id = 0
    for card in state.stadium:
        stadium_id = card.id

    festival_up = (stadium_id == Festival_Grounds)
    no_draw     = (my_state.deckCount <= 5)
    bench_full  = (len(my_state.bench) >= 5)

    # メインアタッカーがベンチにいるか（Dipplin 優先）
    has_dipplin_bench = any(
        c.id == Dipplin and len(c.energies) >= 1 for c in my_state.bench
    )

    # 相手バトルポケモンがexか
    op_active_is_ex = False
    if op_state.active and op_state.active[0] is not None:
        op_active_is_ex = card_table[op_state.active[0].id].ex

    # --- スコアリング ---
    scores = []
    for o in select.option:
        score = 0

        if o.type == OptionType.NUMBER:
            score = o.number

        elif o.type == OptionType.YES:
            score = 1

        elif o.type == OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score = 90000 + len(pokemon.energies) * 10

        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            data = card_table[card.id]

            if data.cardType == CardType.POKEMON:
                # ポケモンをプレイ（バシック → ベンチへ）
                score = 50000
                if card.id == Grookey and field_counts[Grookey] + field_counts[Thwackey] >= 2:
                    score = -1
                elif card.id in (Applin_TWM, Applin_SCR):
                    if field_counts[Applin_TWM] + field_counts[Applin_SCR] + field_counts[Dipplin] >= 4:
                        score = -1
                elif card.id == Goldeen and field_counts[Goldeen] + field_counts[Seaking] >= 1:
                    score = -1
                elif card.id == Rellor and field_counts[Rellor] + field_counts[Rabsca] >= 1:
                    score = -1
                elif card.id == Shaymin and field_counts[Shaymin] >= 1:
                    score = -1

            elif data.cardType == CardType.STADIUM:
                # Festival Grounds を貼る
                if stadium_id == Festival_Grounds:
                    score = -1
                else:
                    score = 70000

            elif data.cardType == CardType.SUPPORTER:
                if state.supporterPlayed:
                    score = -1
                elif no_draw and card.id not in (Lana_Aid, Boss_Orders):
                    score = -1
                elif card.id == Lillie_Det:
                    score = 25000
                elif card.id == Black_Belt:
                    # ex 相手に攻撃できるターンだけ有効
                    score = 26000 if op_active_is_ex else -1
                elif card.id == Boss_Orders:
                    # ベンチに価値ある相手がいる場合
                    score = 22000 if len(op_state.bench) >= 1 else -1
                elif card.id == Lana_Aid:
                    # 捨て札にポケモン or エネルギーがある場合
                    recoverable = sum(
                        v for k, v in discard_counts.items()
                        if k in (Grookey, Applin_TWM, Applin_SCR, Dipplin,
                                 Goldeen, Rellor, Rabsca, Shaymin, Grass_Energy)
                    )
                    score = 20000 if recoverable >= 1 else -1
                elif card.id == Dawn:
                    score = 21000
                elif card.id == Kieran:
                    score = 19000

            else:  # ITEM
                if card.id == Buddy_Poffin:
                    score = 45000 if not bench_full else -1
                elif card.id == Poke_Pad:
                    score = 40000
                elif card.id == Bug_Catching:
                    score = 38000
                elif card.id == Night_Stretcher:
                    recoverable = sum(
                        v for k, v in discard_counts.items()
                        if k in (Dipplin, Goldeen, Seaking, Thwackey,
                                 Grookey, Applin_TWM, Applin_SCR, Grass_Energy)
                    )
                    score = 35000 if recoverable >= 1 else -1
                elif card.id == Secret_Box:
                    # 手札3枚以上の余裕がある時だけ使う
                    score = 30000 if my_state.handCount >= 4 else -1
                elif card.id == Switch_Card:
                    score = 10000 if festival_lead_on_bench else -1

        elif o.type == OptionType.ATTACH:
            card    = get_card(obs, o.area, o.index, my_index)
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            data    = card_table[card.id]

            if data.cardType == CardType.TOOL:
                score = 60000
                if o.inPlayArea == AreaType.ACTIVE:
                    score += 1000
            else:
                energy_count = len(pokemon.energies)
                is_active    = (o.inPlayArea == AreaType.ACTIVE)

                if is_active:
                    if pokemon.id in FESTIVAL_LEAD_IDS:
                        # アタッカーは1枚で十分。2枚目以降は付けない
                        score = 20000 if energy_count == 0 else -1
                    elif pokemon.id == Thwackey:
                        # 逃げるために2枚まで許可
                        score = 10000 if energy_count < 2 else -1
                    else:
                        score = -1
                else:
                    # ベンチ：進化ライン（Applin含む）に1枚だけ準備付け
                    # Applin にエネルギーを付けておくと Dipplin 進化後即攻撃できる
                    if pokemon.id == Dipplin:
                        score = 15000 if energy_count == 0 else -1
                    elif pokemon.id in (Applin_TWM, Applin_SCR):
                        score = 13000 if energy_count == 0 else -1
                    elif pokemon.id in (Goldeen, Seaking):
                        score = 12000 if energy_count == 0 else -1
                    else:
                        score = -1

        elif o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if no_draw:
                score = -1
            elif card.id == Thwackey:
                # Boom Boom Groove: Festival Lead が場にいる時だけ有効
                score = 55000 if active_has_festival_lead else -1
            else:
                score = 30000

        elif o.type == OptionType.RETREAT:
            score = 8000 if festival_lead_on_bench and not active_has_festival_lead else -1

        elif o.type == OptionType.ATTACK:
            score = 1000  # 攻撃はターン最後

        elif o.type == OptionType.CARD:
            card = get_card(obs, o.area, o.index, o.playerIndex)
            if card is None:
                scores.append(0)
                continue

            energy_count = len(card.energies) if isinstance(card, Pokemon) else 0

            if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE,
                           SelectContext.SETUP_ACTIVE_POKEMON):
                # 優先度: Festival Lead アタッカー > 捨て駒 > ベンチ役（Thwackey/Rabsca）
                score = energy_count * 200
                if card.id == Dipplin:                score += 5000
                elif card.id == Seaking:              score += 3000
                elif card.id == Goldeen:              score += 2000
                elif card.id in (Grookey, Applin_TWM, Applin_SCR): score += 500
                elif card.id == Rellor:               score += 300
                elif card.id == Thwackey:             score += 100  # ベンチ特性要員なので前に出したくない
                elif card.id == Rabsca:               score += 50
                elif card.id == Shaymin:              score += 50

            elif context == SelectContext.SETUP_BENCH_POKEMON:
                # 初期ベンチ選択：Festival Lead 持ちを優先
                if card.id in (Applin_TWM, Applin_SCR):
                    score = 500
                elif card.id == Grookey:
                    score = 400
                elif card.id == Goldeen:
                    score = 300
                elif card.id == Rellor:
                    score = 200
                else:
                    score = 100

            elif context in (SelectContext.TO_BENCH, SelectContext.TO_HAND):
                # デッキやディスカードから手札/ベンチへ加えるカードを選ぶ
                # 優先度: Applin > Dipplin > Grookey > Thwackey > その他
                if card.id in (Applin_TWM, Applin_SCR):
                    score = 1000
                elif card.id == Dipplin:
                    score = 900 if field_counts[Applin_TWM] + field_counts[Applin_SCR] >= 1 else 400
                elif card.id == Grookey:
                    score = 800 if field_counts[Grookey] + field_counts[Thwackey] == 0 else 200
                elif card.id == Thwackey:
                    score = 700 if field_counts[Thwackey] == 0 else 100
                elif card.id == Festival_Grounds:
                    score = 600 if not festival_up else 50
                elif card.id == Goldeen:
                    score = 500 if field_counts[Goldeen] + field_counts[Seaking] == 0 else 50
                elif card.id == Rellor:
                    score = 300 if field_counts[Rabsca] + field_counts[Rellor] == 0 else 10
                elif card.id == Grass_Energy:
                    score = 250
                else:
                    score = 100
                # 重複ペナルティ
                if hand_counts.get(card.id, 0) >= 2:
                    score -= 500

            elif context == SelectContext.DISCARD:
                # 捨てるカードを選ぶ：不要なものを優先
                score = 0
                if card.id == Grass_Energy:
                    score = 10   # エネルギーは少ないので温存
                elif card.id in (Dipplin, Thwackey, Rabsca, Shaymin, Festival_Grounds):
                    score = -500  # 重要カードは捨てたくない
                elif card.id in (Grookey, Applin_TWM, Applin_SCR):
                    score = 100 if field_counts.get(card.id, 0) >= 2 else 50
                else:
                    score = 200
                if hand_counts.get(card.id, 0) >= 2:
                    score += 300  # 重複は捨てやすい

        scores.append(score)

    desc_indices = [i for i, _ in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)]

    # minCount 以上 maxCount 以下、スコア負のものは可能な限り除外
    output = []
    for i in desc_indices:
        if len(output) >= select.maxCount:
            break
        if scores[i] >= 0 or len(output) < select.minCount:
            output.append(i)

    return output
