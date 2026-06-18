import os
from collections import defaultdict

from cg.api import (
    AreaType, CardType, Observation, SelectContext, OptionType,
    Card, Pokemon, all_card_data, all_attack, to_observation_class,
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
attack_table = {a.attackId: a for a in all_attack()}

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
    festival_lead_on_bench   = False

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

    # 進化可否（appearThisTurn=True は進化不可）
    grookey_evolvable = any(
        c.id == Grookey and not c.appearThisTurn for c in my_state.bench
    )
    applin_evolvable = any(
        c.id in (Applin_TWM, Applin_SCR) and not c.appearThisTurn for c in my_state.bench
    )
    can_thwackey_combo = (
        active_has_festival_lead
        and grookey_evolvable
        and field_counts[Thwackey] == 0
    )

    # 相手アクティブ情報
    op_active_poke = op_state.active[0] if op_state.active and op_state.active[0] is not None else None
    op_active_is_ex = card_table[op_active_poke.id].ex if op_active_poke else False

    # 自分のアクティブ情報
    my_active_poke = my_state.active[0] if my_state.active and my_state.active[0] is not None else None
    can_attack_now = (
        my_active_poke is not None
        and my_active_poke.id in FESTIVAL_LEAD_IDS
        and len(my_active_poke.energies) >= 1
        and not my_state.asleep
        and not my_state.paralyzed
    )

    my_damage = 0
    if my_active_poke:
        data = card_table[my_active_poke.id]
        my_damage = max(
            (attack_table[aid].damage for aid in data.attacks if aid in attack_table),
            default=0,
        )
        if festival_up:
            my_damage *= 2

    cannot_ko_active = (op_active_poke is None or op_active_poke.hp > my_damage)

    # ================================================================
    # ニーズアセスメント
    # priority 10=今すぐ必要（最高） → 1=あれば嬉しい程度
    # 手札にすでにあるカードは登録しない（TO_HAND で出てこないため不要）
    # ================================================================
    needs: dict[int, int] = {}

    def need(card_id: int, priority: int) -> None:
        """既存より高い優先度の場合のみ更新"""
        if priority > needs.get(card_id, 0):
            needs[card_id] = priority

    # スタジアム（攻撃回数を増やすボーナス。攻撃できること自体より優先度は低い）
    if not festival_up and hand_counts.get(Festival_Grounds, 0) == 0:
        need(Festival_Grounds, 6)

    # Thwackey コンボ（Festival Lead前 + 進化可能 Grookey → 即 Boom Boom Groove）
    if can_thwackey_combo:
        need(Thwackey, 10)

    # 進化先（今すぐ進化可能なら9、次ターン以降なら7）
    applin_in_play = field_counts[Applin_TWM] + field_counts[Applin_SCR]
    if applin_in_play > 0 and field_counts[Dipplin] == 0:
        need(Dipplin, 9 if applin_evolvable else 7)

    if field_counts[Grookey] > 0 and field_counts[Thwackey] == 0:
        need(Thwackey, 9 if grookey_evolvable else 7)

    # ドロー補充（サポーター未使用 + 手札不足）
    if hand_counts.get(Lillie_Det, 0) == 0 and not state.supporterPlayed:
        need(Lillie_Det, 9 if my_state.handCount <= 3 else 6)

    # 退場手段（退場することで攻撃またはコンボが可能になる時のみ高優先）
    bench_fl_can_attack = any(
        c.id in FESTIVAL_LEAD_IDS and len(c.energies) >= 1
        for c in my_state.bench
    )
    bench_fl_enables_combo = (
        field_counts[Thwackey] >= 1
        and any(c.id in FESTIVAL_LEAD_IDS for c in my_state.bench)
    )
    need_retreat = not active_has_festival_lead and (bench_fl_can_attack or bench_fl_enables_combo)
    if need_retreat:
        if hand_counts.get(Air_Balloon, 0) == 0:
            need(Air_Balloon, 8)
        if hand_counts.get(Switch_Card, 0) == 0:
            need(Switch_Card, 6)

    # 基本ポケモン（ベンチに置ける）
    if not bench_full:
        if applin_in_play == 0:
            need(Applin_TWM, 8)
            need(Applin_SCR, 8)
        else:
            need(Applin_TWM, 5)
            need(Applin_SCR, 5)

        if field_counts[Grookey] + field_counts[Thwackey] == 0:
            need(Grookey, 7)

        if field_counts[Goldeen] + field_counts[Seaking] == 0:
            need(Goldeen, 5)

        if field_counts[Rellor] + field_counts[Rabsca] == 0:
            need(Rellor, 3)

    # エネルギー（アタッカーが無エネ）
    attacker_needs_energy = (
        (my_active_poke and my_active_poke.id in FESTIVAL_LEAD_IDS
         and len(my_active_poke.energies) == 0)
        or any(c.id in FESTIVAL_LEAD_IDS and len(c.energies) == 0 for c in my_state.bench)
    )
    need(Grass_Energy, 6 if attacker_needs_energy else 3)

    # どうぐ（アクティブアタッカーがツール未装備）
    if my_active_poke and my_active_poke.id in FESTIVAL_LEAD_IDS and len(my_active_poke.tools) == 0:
        need(Brave_Bangle, 4)
        need(Air_Balloon, 4)  # 退場不要でも装備価値あり（退場必要時は上書きされない）

    # サーチカードの価値計算（PLAY スコア算出用）
    pokemon_need_max = max(
        (p for cid, p in needs.items()
         if cid in card_table and card_table[cid].cardType == CardType.POKEMON),
        default=0,
    )
    any_need_max = max(needs.values(), default=0)
    need_types = {card_table[cid].cardType for cid in needs if cid in card_table}

    # ================================================================
    # スコアリング
    # ================================================================
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
            if pokemon.id in (Applin_TWM, Applin_SCR):
                if field_counts[Dipplin] > 0:
                    score -= 2000
                if not active_has_festival_lead:
                    score += 1000
            elif pokemon.id == Grookey:
                if field_counts[Thwackey] > 0:
                    score -= 2000
                if active_has_festival_lead:
                    score += 1000

        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            data = card_table[card.id]

            if data.cardType == CardType.POKEMON:
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
                score = -1 if stadium_id == Festival_Grounds else 70000

            elif data.cardType == CardType.SUPPORTER:
                if state.supporterPlayed:
                    score = -1
                elif no_draw and card.id not in (Lana_Aid, Boss_Orders):
                    score = -1
                elif card.id == Lillie_Det:
                    score = 25000
                elif card.id == Black_Belt:
                    lillie_available = hand_counts.get(Lillie_Det, 0) > 0
                    use_bb = op_active_is_ex and (bench_full or not lillie_available)
                    score = 24000 if use_bb else -1
                elif card.id == Boss_Orders:
                    bench_ko_targets = [c for c in op_state.bench if c is not None and c.hp <= my_damage]
                    use_boss = can_attack_now and cannot_ko_active and len(bench_ko_targets) >= 1
                    score = 22000 if use_boss else -1
                elif card.id == Lana_Aid:
                    lana_targets = {Grookey, Applin_TWM, Applin_SCR, Dipplin,
                                    Goldeen, Rellor, Rabsca, Shaymin, Grass_Energy}
                    needed_in_discard = sum(
                        discard_counts.get(cid, 0)
                        for cid in needs
                        if cid in lana_targets and needs[cid] >= 5
                    )
                    score = 20000 if needed_in_discard >= 1 else -1
                elif card.id == Dawn:
                    score = 21000 if not bench_full and pokemon_need_max >= 4 else -1
                elif card.id == Kieran:
                    switch_in_hand = hand_counts.get(Air_Balloon, 0) > 0 or hand_counts.get(Switch_Card, 0) > 0
                    score = 19000 if not switch_in_hand else -1

            else:  # ITEM
                if card.id == Buddy_Poffin:
                    # ベンチが薄く進化できる基本もいない → ベーシック2枚展開が急務
                    need_basics = len(my_state.bench) <= 1 and not (grookey_evolvable or applin_evolvable)
                    score = 45000 if (not bench_full and need_basics) else (20000 if not bench_full else -1)
                elif card.id == Poke_Pad:
                    # ポケモンニーズが高いほど急いで使う
                    score = 40000 if pokemon_need_max >= 7 else (28000 if pokemon_need_max >= 4 else 12000)
                elif card.id == Bug_Catching:
                    score = 38000 if pokemon_need_max >= 7 else (25000 if pokemon_need_max >= 4 else 10000)
                elif card.id == Night_Stretcher:
                    recoverable = sum(
                        v for k, v in discard_counts.items()
                        if k in (Dipplin, Goldeen, Seaking, Thwackey,
                                 Grookey, Applin_TWM, Applin_SCR, Grass_Energy)
                    )
                    score = 35000 if recoverable >= 1 else -1
                elif card.id == Secret_Box:
                    # 充足できるカードタイプが多いほど高価値
                    score = 32000 if len(need_types) >= 3 else (28000 if len(need_types) >= 2 else (20000 if any_need_max >= 7 else -1))
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
                        score = 20000 if energy_count == 0 else -1
                    elif pokemon.id == Thwackey:
                        score = 10000 if energy_count < 2 else -1
                    else:
                        score = -1
                else:
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
            if card.id == Thwackey:
                score = 55000 if (active_has_festival_lead and not no_draw) else -1
            elif card.id == Rabsca:
                score = 35000 if op_active_is_ex else 30000
            else:
                score = 30000 if not no_draw else -1

        elif o.type == OptionType.RETREAT:
            score = 8000 if need_retreat else -1

        elif o.type == OptionType.ATTACK:
            score = 1000

        elif o.type == OptionType.CARD:
            card = get_card(obs, o.area, o.index, o.playerIndex)
            if card is None:
                scores.append(0)
                continue

            energy_count = len(card.energies) if isinstance(card, Pokemon) else 0

            if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE,
                           SelectContext.SETUP_ACTIVE_POKEMON):
                if o.playerIndex != my_index:
                    # Boss Orders: KOできるターゲットを最優先、残HPが低いほど高スコア
                    score = (10000 - card.hp) if isinstance(card, Pokemon) and card.hp <= my_damage else 0
                else:
                    # 優先度: Festival Lead アタッカー > 捨て駒 > ベンチ役（Thwackey/Rabsca）
                    score = energy_count * 200
                    if card.id == Dipplin:                              score += 5000
                    elif card.id == Seaking:                            score += 3000
                    elif card.id == Goldeen:                            score += 2000
                    elif card.id in (Grookey, Applin_TWM, Applin_SCR): score += 500
                    elif card.id == Rellor:                             score += 300
                    elif card.id == Thwackey:                           score += 100
                    elif card.id == Rabsca:                             score += 50
                    elif card.id == Shaymin:                            score += 50

            elif context == SelectContext.SETUP_BENCH_POKEMON:
                if card.id in (Applin_TWM, Applin_SCR): score = 500
                elif card.id == Grookey:                score = 400
                elif card.id == Goldeen:                score = 300
                elif card.id == Rellor:                 score = 200
                else:                                   score = 100

            elif context in (SelectContext.TO_BENCH, SelectContext.TO_HAND):
                # ニーズ優先度をそのままスコアに変換（priority 10 → 1000）
                score = needs.get(card.id, 0) * 100
                # 重複ペナルティ（手札に同じカードが2枚以上）
                if hand_counts.get(card.id, 0) >= 2:
                    score -= 300

            elif context == SelectContext.DISCARD:
                score = 0
                if card.id == Festival_Grounds:
                    score = 500 if festival_up else -500
                elif card.id in (Dipplin, Thwackey, Rabsca, Shaymin):
                    score = -500
                elif card.id == Lillie_Det:
                    score = -300 if not state.supporterPlayed else 200
                elif card.id in (Black_Belt, Boss_Orders, Lana_Aid, Dawn, Kieran):
                    score = 300
                elif card.id == Buddy_Poffin:
                    score = 400 if bench_full else 50
                elif card.id == Grass_Energy:
                    score = 10
                elif card.id in (Grookey, Applin_TWM, Applin_SCR):
                    score = 100 if field_counts.get(card.id, 0) >= 2 else 50
                else:
                    score = 200
                if hand_counts.get(card.id, 0) >= 2:
                    score += 300

        scores.append(score)

    desc_indices = [i for i, _ in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)]

    output = []
    for i in desc_indices:
        if len(output) >= select.maxCount:
            break
        if scores[i] >= 0 or len(output) < select.minCount:
            output.append(i)

    return output
