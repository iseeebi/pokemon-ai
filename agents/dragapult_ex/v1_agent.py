"""
Dragapult ex - v3 (Rollout Lookahead Agent)

Key improvements over v2:
1. Rollout-based lookahead (depth=8): resolves Phantom Dive counter sub-decisions
2. _simple_rollout_score: fast heuristic for rollout sub-decisions
3. Fix: Team_Rocket_Watchtower played on turn-1 / to replace opponent stadium
4. Fix: Ultra_Ball requires 2 negative-value cards to play (avoid bad discards)
"""
import os
import random
from collections import defaultdict

from cg.api import (
    AreaType, CardType, Log, LogType, Observation, SelectContext, SelectType, OptionType,
    Card, Pokemon, all_card_data, to_observation_class,
    search_begin, search_step, search_end,
)

file_path = "deck.csv"
if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
with open(file_path, "r", encoding="utf-8-sig") as f:
    my_deck = [int(line.strip()) for line in f if line.strip()]
if len(my_deck) != 60:
    raise ValueError(f"Deck size invalid: {len(my_deck)}")

all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}

Dreepy                 = 119
Drakloak               = 120
Dragapult_ex           = 121
Fezandipiti_ex         = 140
Latias_ex              = 184
Budew                  = 235
Meowth_ex              = 1071
Rare_Candy             = 1079
Unfair_Stamp           = 1080
Buddy_Buddy_Poffin     = 1086
Night_Stretcher        = 1097
Crushing_Hammer        = 1120
Ultra_Ball             = 1121
Poke_Pad               = 1152
Lucky_Helmet           = 1156
Boss_Orders            = 1182
Crispin                = 1198
Brock_Scouting         = 1210
Lillie_Determination   = 1227
Team_Rocket_Watchtower = 1256
Basic_Fire_Energy      = 2
Basic_Psychic_Energy   = 5

UNNECESSARY = -10000000


class AttackPlan:
    attack: int = 0
    counter: list[int] = []


can_switch        = False
can_attack        = False
can_main_attack   = False
can_energy_attach = False
use_support       = 0
bench_attacker    = False
pre_turn_log:     list[Log] = []
current_turn_log: list[Log] = []

prize:       list[int] = []
card_counts: defaultdict = defaultdict(int)
serial_set:  set[int]   = set()
plan_a = AttackPlan()
plan_b = AttackPlan()


def no_damage_dex(id: int) -> bool:
    return id in (158, 207, 330, 345)


def no_damage_counter(pokemon: Pokemon) -> bool:
    if pokemon.id in (28, 199, 203, 207, 362, 1136):
        return True
    for card in pokemon.energyCards:
        if card.id in (11, 20):
            return True
    return False


def prize_count(pokemon: Pokemon, is_attack_damage: bool) -> int:
    data  = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    if is_attack_damage:
        for card in pokemon.energyCards:
            if card.id == 12: count -= 1
        for card in pokemon.tools:
            if card.id == 1172 and "Lillie" in data.name: count -= 1
    return max(0, count)


def pokemon_score(pokemon: Pokemon, is_attack_damage: bool) -> int:
    data  = card_table[pokemon.id]
    score = prize_count(pokemon, is_attack_damage) * 1000
    score += len(pokemon.energies) * 150
    score += len(pokemon.tools) * 100
    if data.stage2:   score += 250
    elif data.stage1: score += 130
    id = pokemon.id
    if id in (144, 322, 323, 337): score -= 200
    if id == 112 and len(pokemon.energies) >= 1: score += 300
    score += pokemon.hp
    return score


def add_card_count(card, my_index: int):
    if card is None: return
    if isinstance(card, Pokemon) or card.playerIndex == my_index:
        if card.serial not in serial_set:
            card_counts[card.id] -= 1
            serial_set.add(card.serial)
    if isinstance(card, Pokemon):
        for c in card.energyCards: add_card_count(c, my_index)
        for c in card.tools:       add_card_count(c, my_index)
        for c in card.preEvolution: add_card_count(c, my_index)


def set_card_counts(obs: Observation, my_index: int):
    card_counts.clear()
    serial_set.clear()
    for id in my_deck:
        card_counts[id] += 1
    state    = obs.current
    my_state = state.players[my_index]
    for card in my_state.hand:    add_card_count(card, my_index)
    for card in my_state.discard: add_card_count(card, my_index)
    for card in my_state.bench:   add_card_count(card, my_index)
    for card in my_state.active:  add_card_count(card, my_index)
    for card in state.stadium:    add_card_count(card, my_index)
    if state.looking:
        for card in state.looking: add_card_count(card, my_index)
    add_card_count(obs.select.effect, my_index)


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


def _simulate_attack(obs: Observation, opt_idx: int) -> tuple[int, bool]:
    """Search API でアタック opt_idx の (ダメージ, KO判定) を返す。失敗時は (0, False)。"""
    state     = obs.current
    mi        = state.yourIndex
    ms        = state.players[mi]
    ops       = state.players[1 - mi]
    op_active = ops.active[0] if ops.active and ops.active[0] is not None else None
    if op_active is None:
        return (0, False)

    initial_hp     = op_active.hp
    initial_prizes = len(ms.prize)
    deck_n  = min(ms.deckCount,  len(my_deck))
    prize_n = min(len(ms.prize), len(my_deck))

    try:
        ss = search_begin(
            obs,
            your_deck      = random.sample(my_deck, deck_n)  if deck_n  > 0 else [],
            your_prize     = random.sample(my_deck, prize_n) if prize_n > 0 else [],
            opponent_deck  = [Basic_Psychic_Energy] * ops.deckCount,
            opponent_prize = [Basic_Psychic_Energy] * len(ops.prize),
            opponent_hand  = [Basic_Psychic_Energy] * ops.handCount,
            opponent_active= [],
        )
        r      = search_step(ss.searchId, [opt_idx])
        new_s  = r.observation.current
        is_ko  = len(new_s.players[mi].prize) < initial_prizes

        if not is_ko:
            noa    = new_s.players[1 - mi].active[0]
            damage = (initial_hp - noa.hp) if (noa is not None and noa.id == op_active.id) else initial_hp
        else:
            damage = initial_hp

        search_end()
        return (damage, is_ko)
    except Exception:
        try: search_end()
        except Exception: pass
        return (0, False)


def main_option_proc(obs: Observation, damage: int):
    state    = obs.current
    select   = obs.select
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]

    global can_switch, can_attack, can_main_attack, can_energy_attach
    can_switch = can_attack = can_main_attack = can_energy_attach = False
    for o in select.option:
        if o.type == OptionType.RETREAT:   can_switch = True
        elif o.type == OptionType.ATTACK:
            can_attack = True
            if o.attackId == 154: can_main_attack = True

    plan_a.attack = plan_b.attack = -1
    if not can_main_attack and not (bench_attacker and can_switch):
        return

    cards = [op_state.active[0]] + list(op_state.bench)
    counter_indices = []
    ci = [0]
    remain_damage = 60
    while ci:
        index = ci[-1]
        hp    = cards[index].hp
        if remain_damage >= hp:
            counter_indices.append(ci.copy())
            if index < len(cards) - 1:
                remain_damage -= hp
                ci.append(index + 1)
                continue
        if index == len(cards) - 1:
            ci.pop()
            if ci: remain_damage += cards[ci[-1]].hp
        if ci: ci[-1] += 1
    counter_indices.append([])

    remain_prize = len(my_state.prize)
    plan_score   = 0
    for i, pokemon in enumerate(cards):
        base_prize_count = 0
        base_score       = pokemon_score(pokemon, True)
        active_damage    = 0 if no_damage_dex(pokemon.id) else damage
        if pokemon.hp <= active_damage:
            base_prize_count += prize_count(pokemon, True)
        else:
            base_score *= active_damage / pokemon.hp
        max_score = base_score
        ci_best   = []
        if remain_prize <= base_prize_count:
            max_score = 50000
        else:
            for indices in counter_indices:
                if i in indices: continue
                p     = base_prize_count
                score = base_score
                for index in indices:
                    p     += prize_count(cards[index], False)
                    score += pokemon_score(cards[index], False)
                if remain_prize <= p:
                    score = 50000
                else:
                    if p >= 2:
                        if remain_prize <= 4: score -= 1200
                    elif p == 1: score -= 300
                    else:        score += 1200
                if max_score < score:
                    max_score = score
                    ci_best   = indices
        if plan_score < max_score:
            plan_score      = max_score
            plan_a.attack   = i
            plan_a.counter  = ci_best
        if i == 0:
            plan_b.attack  = plan_a.attack
            plan_b.counter = plan_a.counter


def _pick(scores: list[int], select) -> list[int]:
    """Select option indices from a score list, respecting maxCount / minCount."""
    output = []
    context = select.context
    sorted_scores = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    for i in range(select.maxCount):
        if (sorted_scores[i][1] >= 0
                or select.minCount > i
                or context not in (SelectContext.TO_BENCH, SelectContext.SETUP_BENCH_POKEMON)):
            output.append(sorted_scores[i][0])
    return output


def _simple_rollout_score(obs: Observation) -> list[int]:
    """Fast simplified scoring for rollout sub-decisions (unused — kept for reference)."""
    state   = obs.current
    select  = obs.select
    context = select.context
    mi      = state.yourIndex
    ms      = state.players[mi]
    ops     = state.players[1 - mi]

    effect_cid = 0 if select.effect is None else select.effect.id
    active_id  = ms.active[0].id if ms.active and ms.active[0] else 0
    has_bench_dex = any(c and c.id == Dragapult_ex and len(c.energies) >= 2
                        for c in (ms.bench or []))
    op_total_energy = sum(len(c.energies) for c in
                          list(ops.active or []) + list(ops.bench or []) if c)
    stadium_id = 0
    for c in state.stadium:
        if c: stadium_id = c.id

    scores = []
    for o in select.option:
        score = 0
        if o.type == OptionType.NUMBER:
            score = o.number
        elif o.type == OptionType.YES:
            score = -1 if context == SelectContext.IS_FIRST else 1
        elif o.type == OptionType.CARD:
            card = get_card(obs, o.area, o.index, o.playerIndex)
            if card is None:
                scores.append(score)
                continue
            energy_count = len(card.energies) if isinstance(card, Pokemon) else 0
            hp           = card.hp           if isinstance(card, Pokemon) else 0
            if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE,
                           SelectContext.SETUP_ACTIVE_POKEMON):
                if o.playerIndex == mi:
                    if   card.id == Dragapult_ex: score = 50000
                    elif card.id == Drakloak:     score = 20000 if energy_count >= 1 else -10000
                    elif card.id == Dreepy:       score = 10000
                    elif card.id == Budew:        score = 30000
                    score += energy_count * 1000 + hp
                else:
                    score = 100000 if plan_a.attack == o.index + 1 else (100000 - hp)
            elif context == SelectContext.SETUP_BENCH_POKEMON:
                score = 0
            elif context in (SelectContext.TO_BENCH, SelectContext.TO_HAND):
                if   card.id in (Dragapult_ex, Drakloak): score = 25000
                elif card.id in (Dreepy, Budew):          score = 20000
                elif isinstance(card, Pokemon):            score = 5000
                else:                                      score = 1000
            elif context == SelectContext.DISCARD:
                if effect_cid == Crispin:
                    score = 100000  # Crispin only shows energy — discard any
                else:
                    if card.id in (Dreepy, Drakloak, Dragapult_ex, Budew):
                        score = -200000
                    elif card.id in card_table and card_table[card.id].cardType == CardType.BASIC_ENERGY:
                        score = -100000
                    else:
                        score = 10000
            elif context in (SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
                if hp > 0 and not no_damage_counter(card):
                    score = 100000 - 10 * hp + pokemon_score(card, False)
                    if context == SelectContext.DAMAGE_COUNTER:
                        if 210 <= hp <= 230:     score += 20000 + hp * 20
                        elif 40 <= hp <= 90:     score += 10000 + hp * 20
                        elif hp <= 30:           score += -10000 + hp * 20
                        if card.id in (133, 351): score += 30000
                    else:
                        index = o.index + 1
                        if index in plan_b.counter:
                            score += 100000
                        else:
                            rem = select.remainDamageCounter * 10
                            if 210 <= hp <= 200 + rem: score += 30000
                            elif 20  <= hp <= 60  + rem: score += 10000
                            elif hp == 10: score -= 100000
                else:
                    score = -1
            elif context == SelectContext.ATTACH_FROM:
                if card.id in (Dragapult_ex, Drakloak):
                    score = 20000 - len(card.energies) * 5000
                elif card.id == Dreepy:
                    score = 5000
        elif o.type in (OptionType.ENERGY_CARD, OptionType.ENERGY):
            if o.playerIndex != mi:
                score = 20 if o.area == AreaType.BENCH else 10
        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, mi)
            if card is None:
                scores.append(score)
                continue
            ctype = card_table[card.id].cardType if card.id in card_table else -1
            if state.supporterPlayed and ctype == CardType.SUPPORTER:
                score = -1
            elif card.id == Rare_Candy:              score = 75000
            elif card.id == Buddy_Buddy_Poffin:      score = 46000
            elif card.id == Poke_Pad:                score = 45000
            elif card.id == Ultra_Ball:              score = 40000
            elif card.id in (Crispin, Lillie_Determination): score = 35000
            elif card.id == Brock_Scouting:          score = 30000
            elif card.id == Night_Stretcher:         score = 30000
            elif card.id == Boss_Orders:             score = 35000
            elif card.id == Unfair_Stamp:            score = 15000
            elif card.id == Crushing_Hammer:
                score = 38000 if op_total_energy > 0 else -1
            elif card.id == Team_Rocket_Watchtower:
                score = 80000 if (stadium_id > 0 or state.turn == 1) else -1
            elif card.id == Lucky_Helmet:            score = 15
            else:                                    score = 10
        elif o.type == OptionType.ATTACH:
            card    = get_card(obs, o.area, o.index, mi)
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, mi)
            if card and pokemon:
                if card.id in card_table and card_table[card.id].cardType == CardType.TOOL:
                    score = 61000 if o.inPlayArea == AreaType.ACTIVE else 60000
                elif pokemon.id == Dragapult_ex:
                    score = 20000 - len(pokemon.energies) * 5000
                elif pokemon.id == Drakloak:
                    score = 15000 - len(pokemon.energies) * 4000
                elif pokemon.id == Dreepy:
                    score = 5000 - len(pokemon.energies) * 3000
                else:
                    score = -1
        elif o.type == OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, mi)
            if pokemon:
                if   pokemon.id == Dreepy:   score = 30000 + len(pokemon.energies)
                elif pokemon.id == Drakloak: score = 70000 + len(pokemon.energies)
                else:                        score = -1
        elif o.type == OptionType.ABILITY:
            score = 40000
        elif o.type == OptionType.RETREAT:
            # Prioritize getting Dragapult_ex to active before attacking
            score = 900000 if (active_id != Dragapult_ex and has_bench_dex) else -1
        elif o.type == OptionType.ATTACK:
            if o.attackId == 154:
                # Phantom Dive: highest priority in rollout — must happen to see prize gains
                score = 1000000
            else:
                score = 2000 + o.attackId  # weaker attacks: low but above END

        scores.append(score)
    return scores


def _rollout(search_id: int, obs: Observation, depth: int, initial_state) -> float:
    """
    Run _simple_rollout_score for up to `depth` steps (within our own turn),
    then evaluate via _board_eval.
    Always sends exactly 1 item per search_step call — multi-select via maxCount
    in a single call causes engine error 4; iterate single selections instead.
    """
    for _ in range(depth):
        state = obs.current
        if state is None or state.result != -1:
            break
        if state.yourIndex != initial_state.yourIndex:
            break
        if not obs.select:
            break
        scores = _simple_rollout_score(obs)
        if not scores:
            break
        # Pick the single best option; engine rejects multi-select in search_step
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        if scores[best_idx] < 0 and obs.select.minCount == 0:
            break  # optional selection with all negative scores → skip
        try:
            r = search_step(search_id, [best_idx])
            obs = r.observation
        except Exception:
            break
    return _board_eval(initial_state, obs.current)


def _lookahead_pick(obs: Observation, scores: list[int]) -> int:
    """
    From the top-K heuristic candidates, simulate each 1 step and pick
    the one with the best board evaluation.  Falls back to heuristic top
    if simulation fails or budget exceeded.
    """
    global _in_search
    state   = obs.current
    mi      = state.yourIndex
    my_s    = state.players[mi]
    op_s    = state.players[1 - mi]

    candidates = sorted(
        [i for i, s in enumerate(scores) if s >= 0],
        key=lambda i: scores[i],
        reverse=True,
    )[:_LOOKAHEAD_TOP_K]

    if len(candidates) <= 1:
        return candidates[0] if candidates else 0

    deck_n  = min(my_s.deckCount,  len(my_deck))
    prize_n = min(len(my_s.prize), len(my_deck))
    fixed_deck  = random.sample(my_deck, deck_n)  if deck_n  > 0 else []
    fixed_prize = random.sample(my_deck, prize_n) if prize_n > 0 else []

    best_score = float('-inf')
    best_idx   = candidates[0]
    t0         = time.time()

    _dbg = []
    for cand in candidates:
        if time.time() - t0 > _LOOKAHEAD_BUDGET:
            break
        try:
            _in_search = True
            ss = search_begin(
                obs,
                your_deck      = fixed_deck,
                your_prize     = fixed_prize,
                opponent_deck  = [Basic_Psychic_Energy] * op_s.deckCount,
                opponent_prize = [Basic_Psychic_Energy] * len(op_s.prize),
                opponent_hand  = [Basic_Psychic_Energy] * op_s.handCount,
                opponent_active= [],
            )
            r  = search_step(ss.searchId, [cand])
            ev = _rollout(ss.searchId, r.observation, _ROLLOUT_DEPTH, state)
            search_end()
            _in_search = False
            o = obs.select.option[cand]
            _dbg.append(f"  cand={cand} type={o.type} score={scores[cand]} ev={ev:.0f}")
            if ev > best_score:
                best_score = ev
                best_idx   = cand
        except Exception as e:
            _in_search = False
            try: search_end()
            except Exception: pass
            _dbg.append(f"  cand={cand} score={scores[cand]} EXC={e}")

    import os as _os
    with open(_os.path.join(_os.path.dirname(__file__), "rollout_debug.txt"), "a") as _f:
        _f.write(f"turn={state.turn} mi={mi} picked={best_idx} score={best_score:.0f}\n")
        _f.write("\n".join(_dbg) + "\n")

    return best_idx


# =========================================================
# Main agent
# =========================================================

def agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return my_deck

    global pre_turn_log, current_turn_log

    state    = obs.current
    select   = obs.select
    context  = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]

    if state.turn == 0:
        prize.clear()
        pre_turn_log.clear()
        current_turn_log.clear()
    else:
        for log in obs.logs:
            current_turn_log.append(log)
            if log.type == LogType.TURN_END:
                pre_turn_log      = current_turn_log
                current_turn_log  = []

    pre_ko  = False
    no_item = False
    for log in pre_turn_log:
        if log.type == LogType.ATTACK:
            if log.attackId == 323: no_item = True
        elif log.type == LogType.MOVE_CARD:
            if (log.playerIndex == my_index
                and log.fromArea in (AreaType.BENCH, AreaType.ACTIVE)
                and log.toArea == AreaType.DISCARD):
                pre_ko = True

    if select.deck is not None:
        set_card_counts(obs, my_index)
        for card in select.deck:
            card_counts[card.id] -= 1
        prize.clear()
        for id in card_counts:
            for _ in range(card_counts[id]):
                prize.append(id)

    set_card_counts(obs, my_index)
    for id in prize:
        card_counts[id] -= 1
    deck_counts = card_counts

    prize_diff = len(my_state.prize) - len(op_state.prize)

    global bench_attacker
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)

    active_id           = 0
    bench_attacker      = False
    can_evolve_dreepy   = False
    evolve_dreepy_count = 0
    can_evolve_drakloak = False

    for card in my_state.active:
        if card is None: continue
        active_id = card.id
        field_counts[card.id] += 1
        if not card.appearThisTurn:
            if card.id == Dreepy:
                can_evolve_dreepy    = True
                evolve_dreepy_count += 1
            elif card.id == Drakloak:
                can_evolve_drakloak = True

    for card in my_state.bench:
        field_counts[card.id] += 1
        if not card.appearThisTurn:
            if card.id == Dreepy:
                can_evolve_dreepy    = True
                evolve_dreepy_count += 1
            elif card.id == Drakloak:
                can_evolve_drakloak = True
        if card.id == Dragapult_ex and len(card.energies) >= 2:
            bench_attacker = True

    main_pokemon_count = field_counts[Dreepy] + field_counts[Drakloak] + field_counts[Dragapult_ex]
    no_more_dex        = (field_counts[Dragapult_ex] * 2 >= len(op_state.prize))

    stadium_id = 0
    for card in state.stadium: stadium_id = card.id

    support_count = 0
    for card in my_state.discard: discard_counts[card.id] += 1

    # --- Simulation: attacks only in MAIN context ---
    attack_option_indices = [i for i, o in enumerate(select.option) if o.type == OptionType.ATTACK]
    sim_info: dict[int, tuple[int, bool]] = {}
    if context == SelectContext.MAIN and attack_option_indices:
        for idx in attack_option_indices:
            sim_info[idx] = _simulate_attack(obs, idx)

    valid_sims = {k: v for k, v in sim_info.items() if v[0] > 0 or v[1]}
    if valid_sims:
        sim_best_damage = max(d for d, _ in valid_sims.values())
        sim_ko_active   = any(k for _, k in valid_sims.values())
    else:
        sim_best_damage = 60   # Phantom Dive direct hit baseline; was 200 (bug)
        sim_ko_active   = False

    # Opponent energy totals for Crushing Hammer decisions
    op_active_energy = len(op_state.active[0].energies) if op_state.active and op_state.active[0] is not None else 0
    op_total_energy  = op_active_energy + sum(len(p.energies) for p in op_state.bench if p is not None)

    def attach_score(attach_id: int, pokemon: Pokemon, active: bool) -> int:
        energy_count = len(pokemon.energies)
        if card_table[attach_id].cardType == CardType.TOOL:
            return 61000 if active else 60000
        if pokemon.id == Budew:
            return -1
        elif pokemon.id in (Meowth_ex, Fezandipiti_ex, Latias_ex):
            if active and not can_switch and not my_state.asleep and not my_state.paralyzed:
                return 22000 if (bench_attacker or field_counts[Budew] >= 1) else 18000
            return -1
        if active and can_main_attack: return -1
        score = 20000
        if energy_count >= 2:
            if active and not can_switch and not my_state.asleep and not my_state.paralyzed:
                score += 200
            else:
                return -1
        elif energy_count == 1:
            if attach_id == pokemon.energyCards[0].id: return -1
            if pokemon.id == Dragapult_ex: score += 250
            elif pokemon.id == Dreepy:     score -= 150
            else:                          score -= 200
            if active: score += 200
        else:
            if active:
                if bench_attacker: score += 400
            else:
                if pokemon.id == Dragapult_ex: score += 150
                elif pokemon.id == Dreepy:     score += 100
                else:                          score += 50
                if bench_attacker: score -= 200
        if no_more_dex and pokemon.id in (Dreepy, Drakloak): score -= 500
        return score

    def hand_score(id: int, ignore_count: bool):
        score = 0
        if id == Dreepy:
            score = 1000 if main_pokemon_count >= 3 else 18000
        elif id == Drakloak:
            score = 20000 if can_evolve_dreepy else 3000
        elif id == Dragapult_ex:
            if no_more_dex:
                score = UNNECESSARY
            elif can_evolve_dreepy and hand_counts[Rare_Candy] >= 1 and not no_item:
                score = 40000
            elif can_evolve_drakloak:
                score = 30000 if field_counts[id] == 0 else (10000 if field_counts[id] == 1 else 50)
            else:
                score = 50 if field_counts[id] >= 2 else 2000
        elif id == Fezandipiti_ex:
            if pre_ko:             score = 50000
            elif prize_diff <= -2: score = 5
            elif len(op_state.prize) == 1: score = UNNECESSARY
        elif id == Latias_ex:
            if active_id in (Fezandipiti_ex, Meowth_ex, Dreepy):
                score = 28000 if field_counts[Drakloak] + field_counts[Dragapult_ex] == 0 else 15000
            else:
                score = 10
        elif id == Budew:
            if field_counts[id] + field_counts[Drakloak] + field_counts[Dragapult_ex] >= 1:
                score = UNNECESSARY
            elif state.turn >= 2:
                score = 30000
        elif id == Meowth_ex:
            if support_count > hand_counts[Boss_Orders] or stadium_id == Team_Rocket_Watchtower:
                score = 5
            elif state.supporterPlayed: score = 40
            else: score = 35000
        elif id == Rare_Candy:
            if no_more_dex: score = UNNECESSARY
            elif can_evolve_dreepy and hand_counts[Dragapult_ex] >= 1: score = 40000
        elif id == Unfair_Stamp:
            if pre_ko:                    score = 80000
            elif len(op_state.prize) == 1: score = UNNECESSARY
            else:                          score = 80
        elif id == Buddy_Buddy_Poffin:
            count = deck_counts[Dreepy]
            if count == 0:
                score = UNNECESSARY
            else:
                if state.turn <= 2 and field_counts[Budew] == 0 and deck_counts[Budew] >= 1:
                    count += 1
                score = 35000 if count >= 2 else 0
        elif id == Night_Stretcher:
            for i in discard_counts:
                if discard_counts[i] >= 1:
                    ct = card_table[i].cardType
                    if ct in (CardType.POKEMON, CardType.BASIC_ENERGY):
                        score = max(score, hand_score(i, ignore_count))
        elif id == Crushing_Hammer:
            # Energy denial is always valuable; scale by opponent total energy
            if op_total_energy >= 2:
                score = 22000
            elif op_total_energy == 1:
                score = 16000
            else:
                score = 20
        elif id == Ultra_Ball:
            # Value: fetch Dreepy early, or anything needed
            if main_pokemon_count <= 2 or field_counts[Dreepy] >= 1 or field_counts[Dragapult_ex] == 0:
                score = 20000
            else:
                score = 5
        elif id == Poke_Pad:
            score = max(hand_score(Dreepy, ignore_count), hand_score(Drakloak, ignore_count))
        elif id == Lucky_Helmet: score = 15
        elif id == Boss_Orders:
            if plan_a.attack > 0: score = 60000
        elif id == Crispin:
            if not ignore_count or support_count == 0:
                if deck_counts[Basic_Fire_Energy] == 0 or deck_counts[Basic_Psychic_Energy] == 0:
                    score = 10
                elif not can_main_attack and not bench_attacker and field_counts[Dragapult_ex] >= 1:
                    score = 55000
                else:
                    score = 25000
        elif id == Brock_Scouting:
            if not ignore_count or support_count == 0:
                if state.turn == 2 and field_counts[Budew] + field_counts[Latias_ex] == 0:
                    score = 50000
                else:
                    score = 30000
        elif id == Lillie_Determination:
            if not ignore_count or support_count == 0: score = 45000
        elif id == Team_Rocket_Watchtower:
            # Play aggressively: any time opponent has no stadium or different stadium
            if stadium_id == Team_Rocket_Watchtower:
                score = 0   # already up
            elif stadium_id == 0:
                score = 15000   # empty field — own it
            else:
                score = 20000   # replace opponent's stadium
        elif id in (Basic_Fire_Energy, Basic_Psychic_Energy):
            if can_main_attack and (len(op_state.prize) <= 2
                or (bench_attacker and len(op_state.prize) <= 4)):
                score = UNNECESSARY
            else:
                max_s = -10000
                for pokemon in my_state.active:
                    if pokemon is None: continue
                    max_s = max(max_s, attach_score(id, pokemon, True))
                for pokemon in my_state.bench:
                    max_s = max(max_s, attach_score(id, pokemon, False))
                score = max_s - 5000
                if can_main_attack or bench_attacker: score //= 10

        if not ignore_count and hand_counts[id] > 0:
            if id == Drakloak and hand_counts[id] < evolve_dreepy_count: score -= 10
            else: score -= 100000
        return score

    global use_support
    if context == SelectContext.MAIN:
        # Fix: pass sim_best_damage (was hardcoded 200 — broke counter-placement planning)
        main_option_proc(obs, sim_best_damage)
        use_support = 0
        if not state.supporterPlayed:
            support_score = 0
            for o in select.option:
                if o.type == OptionType.PLAY:
                    card = get_card(obs, AreaType.HAND, o.index, state.yourIndex)
                    if card_table[card.id].cardType == CardType.SUPPORTER:
                        s = hand_score(card.id, True)
                        if support_score < s:
                            support_score = s
                            use_support   = card.id

    hand_scores            = []
    negative_hand_count    = 0
    for card in my_state.hand:
        s = hand_score(card.id, False)
        hand_scores.append(s)
        if s < 0: negative_hand_count += 1
        hand_counts[card.id] += 1
        if card_table[card.id].cardType == CardType.SUPPORTER and card.id != Boss_Orders:
            support_count += 1

    no_draw         = (my_state.deckCount <= 8)
    do_switch       = (not can_main_attack and (bench_attacker or (active_id != Budew and field_counts[Budew] >= 1 and state.turn >= 2)))
    effect_card_id  = 0 if select.effect is None else select.effect.id
    context_card_id = 0 if select.contextCard is None else select.contextCard.id

    scores = []
    for idx, o in enumerate(select.option):
        score = 0
        if o.type == OptionType.NUMBER:
            score = o.number
        elif o.type == OptionType.YES:
            score = -1 if context == SelectContext.IS_FIRST else 1
        elif o.type == OptionType.CARD:
            card = get_card(obs, o.area, o.index, o.playerIndex)
            if card is not None:
                energy_count = len(card.energies) if isinstance(card, Pokemon) else 0
                hp           = card.hp if isinstance(card, Pokemon) else 0
                if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE,
                               SelectContext.SETUP_ACTIVE_POKEMON):
                    if o.playerIndex == my_index:
                        if card.id == Dreepy:         score += 10000
                        elif card.id == Drakloak:
                            score += 20000 if energy_count >= 1 else -10000
                        elif card.id == Dragapult_ex: score += 50000
                        elif card.id == Budew:
                            score += 100000 if context != SelectContext.SWITCH else (30000 if not bench_attacker else 0)
                        elif card.id == Fezandipiti_ex: score -= 1000
                        elif card.id == Meowth_ex:      score -= 2000
                    else:
                        if plan_a.attack == o.index + 1: score += 100000
                        # Bench targets KO-able by sim damage
                        elif valid_sims and isinstance(card, Pokemon) and card.hp <= sim_best_damage:
                            score += 80000
                    score += energy_count * 1000 + hp
                elif context == SelectContext.SETUP_BENCH_POKEMON:
                    score = -1 if (my_index != state.firstPlayer and card.id == Dreepy) else 0
                elif context in (SelectContext.TO_BENCH, SelectContext.TO_HAND):
                    score = hand_score(card.id, False)
                    hand_counts[card.id] += 1
                    if effect_card_id == Crispin:
                        score = 100000 - hand_score(card.id, True)
                elif context == SelectContext.DISCARD:
                    hand_counts[card.id] -= 1
                    if card_table[card.id].cardType == CardType.SUPPORTER:
                        support_count -= 1
                    score = -hand_score(card.id, False)
                elif context in (SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
                    if hp > 0:
                        score = 100000 - 10 * hp + pokemon_score(card, False)
                        if context == SelectContext.DAMAGE_COUNTER:
                            if 210 <= hp <= 230:
                                score += 20000 + hp * 20
                                if o.area == AreaType.ACTIVE: score += 10000
                            elif 40 <= hp <= 90:  score += 10000 + hp * 20
                            elif hp <= 30:        score += -10000 + hp * 20
                            if card.id in (133, 351): score += 30000
                        else:
                            index = o.index + 1
                            if index in plan_b.counter: score += 100000
                            else:
                                remain_damage = select.remainDamageCounter * 10
                                if 210 <= hp <= 200 + remain_damage:  score += 30000
                                elif 20 <= hp <= 60 + remain_damage:  score += 10000
                                elif hp == 10: score -= 100000
                        if no_damage_counter(card): score = -1
                elif context == SelectContext.ATTACH_FROM:
                    score = attach_score(context_card_id, card, o.area == AreaType.ACTIVE)
                    if card.id == Dragapult_ex: score += 200
        elif o.type in (OptionType.ENERGY_CARD, OptionType.ENERGY):
            if o.playerIndex != state.yourIndex:
                score = 20 if o.area == AreaType.BENCH else 10
                card  = get_card(obs, o.area, o.index, o.playerIndex)
                if card_table[card.id].cardType == CardType.SPECIAL_ENERGY: score += 1
        elif o.type == OptionType.PLAY:
            card       = get_card(obs, AreaType.HAND, o.index, my_index)
            card_score = hand_scores[o.index]
            if card.id == Dreepy:         score = 51000
            elif card.id == Fezandipiti_ex:
                score = 53000 if card_score > 0 else -1
            elif card.id == Latias_ex:
                score = 51000 if active_id not in (Drakloak, Dragapult_ex) else -1
            elif card.id == Budew:
                score = 52000 if (field_counts[Budew] == 0 and field_counts[Dragapult_ex] == 0) else -1
            elif card.id == Meowth_ex:
                if state.supporterPlayed or stadium_id == Team_Rocket_Watchtower:
                    score = -1
                elif support_count == 0: score = 50000
                elif support_count == hand_counts[Boss_Orders] and plan_a.attack > 0: score = 50000
                else: score = -1
            elif card.id == Rare_Candy:
                score = -1 if no_more_dex else 75000
            elif card.id == Unfair_Stamp: score = 70000 if pre_ko else 15000
            elif card.id == Night_Stretcher:
                score = 42000 if card_score >= 18000 else -1
            elif card.id == Crushing_Hammer:
                # Play whenever opponent has energy — energy denial is always good
                if op_total_energy == 0:
                    score = -1
                else:
                    score = 38000  # high priority regardless of game phase
            elif card.id == Boss_Orders:
                score = 35000 if card.id == use_support else -1
            elif card.id == Lillie_Determination:
                score = 14000 if card.id == use_support else -1
            elif card.id == Team_Rocket_Watchtower:
                # Rush on turn 1; replace opponent's stadium immediately
                score = 80000 if (stadium_id > 0 or state.turn == 1) else -1
            elif no_draw: score = -1
            elif card.id == Buddy_Buddy_Poffin:
                score = 46000 if deck_counts[Dreepy] > 0 else -1
            elif card.id == Ultra_Ball:
                # Need 2 bad cards to discard — require 2 negative-value cards
                if negative_hand_count >= 2:
                    score = 44000
                elif main_pokemon_count <= 1 and negative_hand_count >= 1:
                    score = 30000  # desperate: only 1 Dreepy/Drakloak on field
                else:
                    score = -1
            elif card.id == Poke_Pad:
                score = 45000 if deck_counts[Dreepy] + deck_counts[Drakloak] > 0 else -1
            elif card.id in (Crispin, Brock_Scouting):
                score = 35000 if card.id == use_support else -1
        elif o.type == OptionType.ATTACH:
            card    = get_card(obs, o.area, o.index, my_index)
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score   = attach_score(card.id, pokemon, o.inPlayArea == AreaType.ACTIVE)
        elif o.type == OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score  += len(pokemon.energies)
            if pokemon.id == Dreepy:
                score += 30000
            elif field_counts[Dragapult_ex] >= 2 or (field_counts[Dragapult_ex] == 1 and len(op_state.prize) <= 2):
                score = -1
            else:
                score += 70000
        elif o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if no_draw:           score = -1
            elif card.id == 1267: score = 1
            else:                 score = 40000
        elif o.type == OptionType.RETREAT:
            score = 10000 if do_switch else -1
        elif o.type == OptionType.ATTACK:
            if idx in sim_info:
                d, ko = sim_info[idx]
                if ko:
                    score = 8000
                elif d > 0:
                    score = 1000 + min(d * 10, 4000)
                else:
                    score = o.attackId
            else:
                score = o.attackId

        scores.append(score)

    return _pick(scores, select)
