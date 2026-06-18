import os
import sys
from collections import defaultdict

from cg.api import AreaType, CardType, Observation, SelectContext, OptionType, Card, Pokemon, all_card_data, to_observation_class

all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}

Iono_Voltorb        = 265   # ×3
Iono_Tadbulb        = 268   # ×3
Iono_Bellibolt_ex   = 269   # ×3
Iono_Wattrel        = 270   # ×3
Iono_Kilowattrel    = 271   # ×3
Buddy_Buddy_Poffin  = 1086  # ×3
Night_Stretcher     = 1097  # ×2
Max_Rod             = 1110  # ×1
Energy_Retrieval    = 1118  # ×1
Ultra_Ball          = 1121  # ×3
Poke_Pad            = 1152  # ×2
Lillie_Determination = 1227 # ×4
Canari              = 1233  # ×4
Levincia            = 1254  # ×3
Basic_Lightning_Energy = 4  # ×22

my_deck = (
    [Iono_Voltorb] * 3 +
    [Iono_Tadbulb] * 3 +
    [Iono_Bellibolt_ex] * 3 +
    [Iono_Wattrel] * 3 +
    [Iono_Kilowattrel] * 3 +
    [Buddy_Buddy_Poffin] * 3 +
    [Night_Stretcher] * 2 +
    [Max_Rod] * 1 +
    [Energy_Retrieval] * 1 +
    [Ultra_Ball] * 3 +
    [Poke_Pad] * 2 +
    [Lillie_Determination] * 4 +
    [Canari] * 4 +
    [Levincia] * 3 +
    [Basic_Lightning_Energy] * 22
)

can_attack = False


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
    op_prize = len(op_state.prize)

    field_counts      = defaultdict(int)
    field_hand_counts = defaultdict(int)
    active_attacker   = False
    bench_attacker    = False

    energy_count = 0
    can_ability  = False
    for p in my_state.active:
        if p is None:
            continue
        field_counts[p.id] += 1
        field_hand_counts[p.id] += 1
        energy_count += len(p.energies)
        if p.id == Iono_Kilowattrel and len(p.energies) > 0:
            can_ability = True
        if p.id == Iono_Voltorb and len(p.energies) >= 2:
            active_attacker = True
    for p in my_state.bench:
        field_counts[p.id] += 1
        field_hand_counts[p.id] += 1
        energy_count += len(p.energies)
        if p.id == Iono_Kilowattrel and len(p.energies) > 0:
            can_ability = True
        if p.id == Iono_Voltorb and len(p.energies) >= 2:
            bench_attacker = True

    field_pokemon1  = field_counts[Iono_Tadbulb] + field_counts[Iono_Bellibolt_ex]
    field_pokemon2  = field_counts[Iono_Wattrel]  + field_counts[Iono_Kilowattrel]
    no_more_pokemon = len(my_state.bench) >= 5
    if field_counts[Iono_Tadbulb] + field_counts[Iono_Wattrel] >= 1:
        no_more_pokemon = False

    stadium_id = 0
    for c in state.stadium:
        stadium_id = c.id

    hand_counts       = defaultdict(int)
    hand_scores       = []
    unused_hand_count = 0
    for c in my_state.hand:
        score = -10000
        if c.id == Iono_Voltorb:           score = 100
        elif c.id == Iono_Bellibolt_ex:
            score = 120 if field_counts[c.id] <= 1 else -10000
        elif c.id == Iono_Kilowattrel:
            score = 140 if field_counts[c.id] <= 1 else -10000
        elif c.id == Ultra_Ball:
            score = 10 if not no_more_pokemon else -10000
        elif c.id == Night_Stretcher:      score = 50
        elif c.id == Energy_Retrieval:     score = 20
        elif c.id == Max_Rod:              score = 1000
        elif c.id == Lillie_Determination: score = 150
        elif c.id == Canari:               score = 160
        elif c.id == Levincia:
            score = 30 if stadium_id != Levincia else -10000
        elif c.id == Basic_Lightning_Energy: score = -10
        score -= hand_counts[c.id] * 100
        hand_scores.append(score)
        if score < 0:
            unused_hand_count += 1
        hand_counts[c.id] += 1
        field_hand_counts[c.id] += 1

    discard_counts = defaultdict(int)
    for c in my_state.discard:
        discard_counts[c.id] += 1

    global can_attack
    if context == SelectContext.MAIN:
        can_attack = False
        for o in select.option:
            if o.type == OptionType.ATTACK:
                can_attack = True

    op_active_hp = 10000
    if op_state.active and op_state.active[0] is not None:
        op_active_hp = op_state.active[0].hp

    no_draw = (my_state.deckCount <= 5)

    scores    = []
    id_counts = defaultdict(int)
    for o in select.option:
        score = 0
        if o.type == OptionType.NUMBER:
            score = o.number
        elif o.type == OptionType.YES:
            score = 1
        elif o.type == OptionType.ATTACH or context == SelectContext.ATTACH_FROM:
            if o.type == OptionType.ATTACH:
                p = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            else:
                p = get_card(obs, o.area, o.index, o.playerIndex)
            score = 40000
            if p.id == Iono_Voltorb:
                if len(p.energies) >= 2:
                    score += 3000 if (o.inPlayArea == AreaType.ACTIVE and not can_attack) else 0
                else:
                    if o.inPlayArea == AreaType.ACTIVE:    score += 5000
                    elif bench_attacker or active_attacker: score += 100
                    else:                                   score += 1000
            elif p.id == Iono_Tadbulb:
                score += 10 - len(p.energies)
            elif p.id == Iono_Bellibolt_ex:
                if len(p.energies) >= 4:
                    score += 500 if (o.inPlayArea == AreaType.ACTIVE and not can_attack) else 0
                else:
                    if o.inPlayArea == AreaType.ACTIVE:    score += 800
                    elif bench_attacker or active_attacker: score += 14 - len(p.energies)
                    else:                                   score += 100
            elif p.id == Iono_Wattrel:
                if len(p.energies) >= 1 or o.inPlayArea == AreaType.ACTIVE:
                    score += 10 - len(p.energies)
                else:
                    score += 6000
            elif p.id == Iono_Kilowattrel:
                score += (11 - len(p.energies)) if len(p.energies) >= 1 else 8000
        elif o.type == OptionType.CARD:
            c = get_card(obs, o.area, o.index, o.playerIndex)
            if c is not None:
                if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE,
                               SelectContext.SETUP_ACTIVE_POKEMON):
                    energy = len(c.energies) if isinstance(c, Pokemon) else 0
                    score -= c.hp if isinstance(c, Pokemon) else 0
                    score -= energy * 100
                    if c.id == Iono_Voltorb:
                        score += 100000 if (20 + energy_count * 20 >= op_active_hp) else 1500
                        if energy >= 1:
                            score += 200
                            if energy >= 2: score += 10000
                    elif c.id == Iono_Bellibolt_ex:
                        score += 1000
                        if energy >= 4: score += 1000
                    elif c.id == Iono_Tadbulb:
                        score += 10
                elif context in (SelectContext.TO_HAND, SelectContext.TO_BENCH):
                    if c.id == Basic_Lightning_Energy:
                        score += 1
                    elif c.id == Iono_Voltorb:
                        if o.area == AreaType.DISCARD:   score += 100000
                        if field_counts[c.id] == 0:      score += 110
                        elif field_counts[c.id] == 1 and op_prize >= 2: score += 5
                    elif c.id == Iono_Tadbulb:
                        if field_pokemon1 == 0:          score += 200
                        elif field_pokemon1 == 1:
                            if op_prize >= 3 or (op_prize >= 2 and field_counts[Iono_Bellibolt_ex] == 0):
                                score += 20
                    elif c.id == Iono_Bellibolt_ex:
                        if field_hand_counts[c.id] == 0:
                            score += 250
                            if field_counts[Iono_Tadbulb] > 0: score += 300
                        elif field_hand_counts[c.id] == 1 and op_prize >= 3:
                            score += 30
                            if field_counts[Iono_Tadbulb] > 0: score += 30
                    elif c.id == Iono_Wattrel:
                        score += 320 if field_pokemon2 == 0 else 15
                    elif c.id == Iono_Kilowattrel:
                        if field_hand_counts[c.id] == 0:
                            score += 300
                            if field_counts[Iono_Wattrel] > 0: score += 250
                        elif field_hand_counts[c.id] == 1:
                            score += 25
                            if field_counts[Iono_Wattrel] > 0: score += 25

                    if c.id != Basic_Lightning_Energy:
                        if hand_counts[c.id] >= 2:   score -= 20000
                        elif hand_counts[c.id] >= 1: score -= 2000
                        if id_counts[c.id] == 1:     score -= 1000
                        elif id_counts[c.id] >= 2:   score -= 10000
                    id_counts[c.id] += 1
                elif context == SelectContext.DISCARD:
                    if o.area == AreaType.HAND and o.playerIndex == my_index:
                        score = -hand_scores[o.index]
        elif o.type == OptionType.PLAY:
            c    = get_card(obs, AreaType.HAND, o.index, my_index)
            data = card_table[c.id]
            if data.cardType == CardType.STADIUM:
                score = 85000 if (discard_counts[Basic_Lightning_Energy] >= 1 or can_ability) else -1
            elif data.cardType == CardType.SUPPORTER:
                score = 25000
                if c.id == Lillie_Determination:    score += 1000
                elif no_draw:                        score = -1
                elif c.id == Canari:
                    if no_more_pokemon:              score = -1
                    elif (field_counts[Iono_Voltorb] > 0
                          and field_counts[Iono_Bellibolt_ex] > 0
                          and field_counts[Iono_Kilowattrel] > 0): score += 100
                    else:                            score += 2000
            elif data.cardType == CardType.POKEMON:
                score = 100000
                if c.id == Iono_Voltorb and field_counts[Iono_Voltorb] >= 2:       score = -1
                elif c.id == Iono_Tadbulb and field_pokemon1 >= 2:                  score = -1
                elif c.id == Iono_Wattrel and field_pokemon2 >= 2:
                    if op_prize >= 2 or field_counts[Iono_Voltorb] == 0 or field_counts[Iono_Bellibolt_ex] == 0:
                        score = -1
            else:
                if c.id == Night_Stretcher:
                    ok = (discard_counts[Iono_Voltorb] > 0
                          or (discard_counts[Iono_Bellibolt_ex] > 0 and field_counts[Iono_Tadbulb] > 0)
                          or (discard_counts[Iono_Kilowattrel] > 0 and field_counts[Iono_Wattrel] > 0))
                    score = 75000 if ok else -1
                elif c.id == Energy_Retrieval: score = 61000
                elif c.id == Max_Rod:
                    score = 55000 if (state.turn >= 3 and discard_counts[Basic_Lightning_Energy] >= 2) else -1
                elif no_draw:                  score = -1
                elif c.id == Buddy_Buddy_Poffin: score = 80000
                elif c.id == Ultra_Ball:
                    if no_more_pokemon or state.turn <= 2: score = -1
                    elif (field_hand_counts[Iono_Bellibolt_ex] > 0
                          and field_hand_counts[Iono_Kilowattrel] > 0):
                        score = 45000 if unused_hand_count >= 2 else -1
                    else:
                        score = 62000 if unused_hand_count >= 1 else -1
                elif c.id == Poke_Pad: score = 79000
        elif o.type == OptionType.EVOLVE:
            score = 110000
        elif o.type == OptionType.ABILITY:
            score = -1
            c = get_card(obs, o.area, o.index, my_index)
            if c.id == Iono_Bellibolt_ex:   score = 50000
            elif c.id == Levincia:          score = 8000
            elif not no_draw and c.id == Iono_Kilowattrel: score = 30000
        elif o.type == OptionType.RETREAT:
            score = 10000 if (bench_attacker and not active_attacker) else -1
        elif o.type == OptionType.ATTACK:
            score = o.attackId

        scores.append(score)

    desc_indices = [i for i, _ in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)]
    return desc_indices[:select.maxCount]
