"""
インタラクティブ対戦ランナー（Dragapult ex） — ターン方針モード

Usage（agents/dragapult_ex/ から実行）:
  python play.py                            # vs Mega Lucario ex
  python play.py --opp mega_abomasnow --games 3
  python play.py --log my_log.json

ターン開始時の入力:
  Enter                     エージェントに全部任せる
  「Crispin使って攻撃」      自然文で方針を指定
  a                         ゲーム内残り全て自動
  q                         終了

方針テキストのパース例:
  "Crispinを使ってドラパルトに炎エネ付けて攻撃"
    → ["Crispinを使って", "ドラパルトに炎エネ付けて", "攻撃"]
  "ボスでSnoverを引っ張って攻撃"
    → ["ボスでSnoverを引っ張って", "攻撃"]
  "Rare Candy→進化→エネ付け"
    → ["Rare Candy", "進化", "エネ付け"]
"""
import os, sys, json, argparse, re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, "submission"))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_ROOT, "opponents"))
os.chdir(_HERE)

from cg.api import (
    AreaType, SelectContext, OptionType,
    Pokemon, all_card_data, to_observation_class
)
from cg.game import battle_start, battle_select, battle_finish
import main as my_module

# ──────────────────────────────────────────────
# カード名テーブル
# ──────────────────────────────────────────────
_all_card  = all_card_data()
CARD_NAME  = {c.cardId: c.name for c in _all_card}
_SYM = {"G":"草","R":"炎","W":"水","L":"雷","P":"超","F":"闘","D":"悪","M":"鋼","Y":"妖","N":"竜","C":"無"}

CTX_LABEL = {
    SelectContext.MAIN:                 "メイン",
    SelectContext.SETUP_ACTIVE_POKEMON: "バトル場(初期)",
    SelectContext.SETUP_BENCH_POKEMON:  "ベンチ(初期)",
    SelectContext.SWITCH:               "バトル場に出す(指定)",
    SelectContext.TO_ACTIVE:            "バトル場に出す",
    SelectContext.TO_BENCH:             "ベンチ/手札へ",
    SelectContext.TO_HAND:              "手札に加える",
    SelectContext.DISCARD:              "トラッシュ",
    SelectContext.DAMAGE_COUNTER:       "ダメカン",
    SelectContext.DAMAGE_COUNTER_ANY:   "ダメカン(自由)",
    SelectContext.ATTACH_FROM:          "エネ付け先",
}


def cname(card_id: int, maxlen: int = 0) -> str:
    raw = CARD_NAME.get(card_id, f"ID:{card_id}")
    m = re.match(r'Basic \{(\w)\} Energy', raw)
    if m:
        return f"{_SYM.get(m.group(1), m.group(1))}エネ"
    name = re.sub(r'\{(\w)\}', lambda x: _SYM.get(x.group(1), x.group(1)), raw)
    if maxlen and len(name) > maxlen:
        return name[:maxlen - 1] + "…"
    return name


def energy_str(poke: Pokemon) -> str:
    try:
        cards = poke.energyCards
        if not cards:
            return "なし"
        from collections import Counter
        cnt = Counter()
        for e in cards:
            lbl = _SYM.get(e.id, CARD_NAME.get(e.id, f"?{e.id}")[:3])
            cnt[lbl] += 1
        return " ".join(f"{l}×{c}" for l, c in cnt.items())
    except Exception:
        n = len(poke.energies) if poke.energies else 0
        return f"{n}個" if n else "なし"


# ──────────────────────────────────────────────
# 選択肢テキスト
# ──────────────────────────────────────────────
def _card_at(st, area, idx, pidx, obs=None):
    try:
        if area == AreaType.DECK:
            if obs is not None and obs.select and obs.select.deck:
                return obs.select.deck[idx]
            return None
        p = st.players[pidx]
        match area:
            case AreaType.HAND:    return p.hand[idx]
            case AreaType.ACTIVE:  return p.active[idx]
            case AreaType.BENCH:   return p.bench[idx]
            case AreaType.DISCARD: return p.discard[idx]
            case AreaType.PRIZE:   return p.prize[idx]
            case _:                return None
    except Exception:
        return None


def opt_text(obs, o, mi: int) -> str:
    st = obs.current

    def hcard():
        c = _card_at(st, AreaType.HAND, o.index, mi)
        return cname(c.id) if c else "?"

    def inplay():
        c   = _card_at(st, o.inPlayArea, o.inPlayIndex, mi)
        loc = "バトル場" if o.inPlayArea == AreaType.ACTIVE else f"ベンチ{o.inPlayIndex}"
        return (cname(c.id) if c else "?"), loc

    t = o.type
    if   t == OptionType.PLAY:    return f"[使う] {hcard()}"
    elif t == OptionType.EVOLVE:
        tgt, loc = inplay()
        return f"[進化] {loc}{tgt} → {hcard()}"
    elif t == OptionType.ATTACH:
        tgt, loc = inplay()
        pidx = getattr(o, "playerIndex", mi)
        c    = _card_at(st, o.area, o.index, pidx, obs)
        src  = cname(c.id) if c else "?"
        return f"[付ける] {src} → {loc}{tgt}"
    elif t == OptionType.ATTACK:  return f"[攻撃] id={o.attackId}"
    elif t == OptionType.RETREAT: return "[退場]"
    elif t == OptionType.ABILITY:
        c = _card_at(st, o.area, o.index, mi)
        return f"[特性] {cname(c.id) if c else '?'}"
    elif t == OptionType.CARD:
        pidx  = getattr(o, "playerIndex", mi)
        c     = _card_at(st, o.area, o.index, pidx, obs)
        side  = "自" if pidx == mi else "相"
        albl  = str(o.area).split(".")[-1]
        return f"[選択:{side}/{albl}] {cname(c.id) if c else '?'}"
    elif t == OptionType.YES:     return "[はい]"
    elif t == OptionType.NUMBER:  return f"[数値:{getattr(o,'number','?')}]"
    elif t == OptionType.ENERGY_CARD:
        pidx = getattr(o, "playerIndex", mi)
        c    = _card_at(st, o.area, o.index, pidx, obs)
        return f"[エネ選択] {cname(c.id) if c else '?'}"
    else:
        return f"[{str(t).split('.')[-1]}]"


# ──────────────────────────────────────────────
# 盤面表示（ターン開始時のみ）
# ──────────────────────────────────────────────
W = 56

def display(obs, scores: list, agent_top: list[int]) -> None:
    st  = obs.current
    sel = obs.select
    mi  = st.yourIndex
    oi  = 1 - mi
    mps = st.players[mi]
    ops = st.players[oi]

    ctx_str   = CTX_LABEL.get(sel.context, str(sel.context).split(".")[-1])
    first_str = "後攻" if st.firstPlayer != mi else "先攻"

    print()
    print("═" * W)
    print(f"  ターン {st.turn}  {first_str}  ▶ {ctx_str}")
    print(f"  サイド  自分:{len(mps.prize)}枚  相手:{len(ops.prize)}枚  デッキ:{mps.deckCount}枚")
    print("═" * W)

    print("【自分】")
    for poke in mps.active:
        if poke:
            ev = " ※登場直後" if getattr(poke, "appearThisTurn", False) else ""
            print(f"  バトル場: {cname(poke.id)}  HP:{poke.hp}  エネ:{energy_str(poke)}{ev}")
    for i, poke in enumerate(mps.bench):
        if poke:
            ev = " ※登場直後" if getattr(poke, "appearThisTurn", False) else ""
            print(f"  ベンチ {i}: {cname(poke.id)}  HP:{poke.hp}  エネ:{energy_str(poke)}{ev}")
    print(f"  手札({len(mps.hand)}枚): {', '.join(cname(c.id) for c in mps.hand) or 'なし'}")

    print("【相手】")
    for poke in ops.active:
        if poke:
            print(f"  バトル場: {cname(poke.id)}  HP:{poke.hp}  エネ:{energy_str(poke)}")
    for i, poke in enumerate(ops.bench):
        if poke:
            print(f"  ベンチ {i}: {cname(poke.id)}  HP:{poke.hp}  エネ:{energy_str(poke)}")
    print(f"  手札:{ops.handCount}枚  デッキ残:{ops.deckCount}枚")

    agent_set = set(agent_top)
    min_c, max_c = sel.minCount, sel.maxCount
    print()
    print(f"【MAIN 選択肢】  (min:{min_c} max:{max_c})")
    for idx, o in enumerate(sel.option):
        sc   = scores[idx] if idx < len(scores) else 0
        mark = "★" if idx in agent_set else " "
        neg  = "  ✗" if sc < 0 else ""
        desc = opt_text(obs, o, mi)
        print(f"  {mark}{idx:3d}: {desc:<38}  score:{sc:>13,.0f}{neg}")


# ──────────────────────────────────────────────
# 方針パース
# ──────────────────────────────────────────────
# カード名の日本語エイリアス → 英語フラグメント
_ALIASES: dict[str, str] = {
    "ドラパルト": "dragapult",
    "ドラクロー": "drakloak",
    "ドリーミー": "dreepy",
    "クリスピン": "crispin",
    "ボス":       "boss",
    "ポフィン":   "poffin",
    "ハンマー":   "hammer",
    "ヘルメット": "helmet",
    "スタンプ":   "stamp",
    "パッド":     "pad",
    "ストレッチャー": "stretcher",
    "ウルトラ":   "ultra",
    "バドウ":     "budew",
    "フェザー":   "fezandipiti",
    "ラティアス": "latias",
    "ニャース":   "meowth",
    "キャンディ": "candy",
    "ウォッチタワー": "watchtower",
    "リリィ":     "lillie",
    "ブロック":   "brock",
    "炎エネ":     "炎エネ",
    "超エネ":     "超エネ",
}

# 方針テキストを分割するパターン（動詞テ形・読点・矢印）
_SPLIT_PAT = re.compile(
    r'[、，→]\s*'
    r'|(?:を使って|使って|付けて|置いて|引っ張って|してから|して|から|次に|その後|そして|最後に)\s*'
)


def parse_policy(text: str) -> list[str]:
    parts = _SPLIT_PAT.split(text)
    return [p.strip() for p in parts if p.strip()]


def _apply_aliases(text: str) -> str:
    t = text.lower()
    for ja, en in _ALIASES.items():
        t = t.replace(ja.lower(), en.lower())
    return t


def match_option(intent: str, obs) -> list[int] | None:
    """方針フラグメント intent に最もマッチする選択肢インデックスを返す。"""
    options = obs.select.option
    mi      = obs.current.yourIndex
    il      = _apply_aliases(intent)

    # 攻撃
    if re.search(r'攻撃|アタック|attack', il):
        for i, o in enumerate(options):
            if o.type == OptionType.ATTACK:
                return [i]

    # 退場
    if re.search(r'退場|逃げ|にげ|retreat', il):
        for i, o in enumerate(options):
            if o.type == OptionType.RETREAT:
                return [i]

    # エネルギー付け
    if re.search(r'エネ付け|エネルギー付け|attach.*energy|energy.*attach', il):
        for i, o in enumerate(options):
            if o.type == OptionType.ATTACH:
                return [i]

    # 進化
    if re.search(r'進化|evolve', il):
        for i, o in enumerate(options):
            if o.type == OptionType.EVOLVE:
                return [i]

    # カード名マッチ（PLAY / EVOLVE / ATTACH / ATTACK）
    # 最も長くマッチした単語を持つ選択肢を返す
    best_i   = None
    best_len = 0
    for i, o in enumerate(options):
        if o.type not in (OptionType.PLAY, OptionType.EVOLVE,
                          OptionType.ATTACH, OptionType.ATTACK):
            continue
        desc_raw = _apply_aliases(opt_text(obs, o, mi))
        for word in re.split(r'\s+', il):
            if len(word) >= 2 and word in desc_raw and len(word) > best_len:
                best_len = len(word)
                best_i   = i

    return [best_i] if best_i is not None else None


# ──────────────────────────────────────────────
# ターン方針の状態
# ──────────────────────────────────────────────
_turn_state: dict = {
    "turn":    -1,
    "intents": [],
    "idx":     0,
}
_auto_mode = False


def _consume_intent(obs, agent_choice: list[int]) -> list[int]:
    """方針リストの次のインテントを消費して選択肢を返す。"""
    intents = _turn_state["intents"]
    while _turn_state["idx"] < len(intents):
        intent = intents[_turn_state["idx"]]
        _turn_state["idx"] += 1
        choice = match_option(intent, obs)
        if choice is not None:
            desc = opt_text(obs, obs.select.option[choice[0]], obs.current.yourIndex)
            n    = _turn_state["idx"]
            tot  = len(intents)
            print(f"  [方針 {n}/{tot}] 「{intent}」→ {desc}")
            return choice
        else:
            print(f"  [方針 skip] 「{intent}」→ 選択肢なし")
    # 方針消化完了 → エージェント
    return agent_choice


def _ask_policy(obs, agent_choice: list[int], scores: list) -> list[int]:
    """ターン開始時に方針を入力してもらい、最初のアクションを返す。"""
    global _auto_mode
    print()
    print("今ターンの方針 (例: 「Crispin使って炎エネ付けて攻撃」)")
    print("  Enter=エージェント任せ  a=ゲーム内全自動  q=終了")
    print("  > ", end="", flush=True)

    while True:
        try:
            raw = sys.stdin.readline().rstrip("\n").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raw = ""

        if raw == "q":
            sys.exit(0)
        elif raw == "a":
            _auto_mode = True
            _turn_state["intents"] = []
            return agent_choice
        elif raw == "":
            _turn_state["intents"] = []
            return agent_choice
        else:
            intents = parse_policy(raw)
            _turn_state["intents"] = intents
            _turn_state["idx"]     = 0
            print(f"  → 方針を {len(intents)} ステップに分解: {intents}")
            return _consume_intent(obs, agent_choice)


# ──────────────────────────────────────────────
# ログ
# ──────────────────────────────────────────────
_log: list[dict] = []
_game_id = 0


def _log_add(obs, scores, agent_choice, human_choice, policy_text=""):
    st  = obs.current
    sel = obs.select
    _log.append({
        "game_id":      _game_id,
        "turn":         st.turn,
        "context":      str(sel.context).split(".")[-1],
        "agent_choice": agent_choice,
        "human_choice": human_choice,
        "overridden":   sorted(human_choice) != sorted(agent_choice),
        "policy":       policy_text,
        "result":       None,
    })


def _mark_result(r: str):
    for e in _log:
        if e["game_id"] == _game_id and e["result"] is None:
            e["result"] = r


# ──────────────────────────────────────────────
# エージェント本体
# ──────────────────────────────────────────────
def interactive_agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return my_module.my_deck

    ctx          = obs.select.context
    agent_choice = my_module.agent(obs_dict)
    scores       = list(getattr(my_module, "_debug_scores", []))

    # 全自動モード
    if _auto_mode:
        _log_add(obs, scores, agent_choice, agent_choice)
        return agent_choice

    # MAIN 以外は常に自動（サブ決断）
    if ctx != SelectContext.MAIN:
        _log_add(obs, scores, agent_choice, agent_choice)
        return agent_choice

    turn = obs.current.turn

    # ターン最初の MAIN → 盤面表示・方針入力
    if turn != _turn_state["turn"]:
        _turn_state["turn"] = turn
        _turn_state["intents"] = []
        _turn_state["idx"]     = 0
        display(obs, scores, agent_choice)
        choice = _ask_policy(obs, agent_choice, scores)
    else:
        # 同ターンの 2 回目以降 MAIN → 方針から続行
        choice = _consume_intent(obs, agent_choice)

    _log_add(obs, scores, agent_choice, choice)
    return choice


# ──────────────────────────────────────────────
# ゲームループ
# ──────────────────────────────────────────────
def run_game(opp_agent, opp_deck) -> str:
    global _game_id, _auto_mode
    _game_id  += 1
    _auto_mode  = False

    obs_dict, _ = battle_start(my_module.my_deck, opp_deck)
    if obs_dict is None:
        return "ERROR"

    agents = [interactive_agent, opp_agent]
    for _ in range(5000):
        current = obs_dict.get("current")
        if current and current.get("result", -1) != -1:
            battle_finish()
            outcome = "WIN" if current["result"] == 0 else "LOSE"
            _mark_result(outcome)
            print()
            print("═" * W)
            print(f"  ゲーム {_game_id} 終了:  {'WIN' if outcome == 'WIN' else 'LOSE'}")
            print("═" * W)
            return outcome
        pidx = current["yourIndex"] if current else 0
        try:
            action   = agents[pidx](obs_dict)
            obs_dict = battle_select(action)
        except SystemExit:
            battle_finish()
            raise
        except Exception as e:
            import traceback
            print(f"\n[ERROR] player={pidx}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            battle_finish()
            _mark_result("ERROR")
            return "ERROR"

    battle_finish()
    _mark_result("DRAW")
    return "DRAW"


# ──────────────────────────────────────────────
# エントリポイント
# ──────────────────────────────────────────────
def main():
    choices = ["dragapult_ex", "iono", "mega_lucario", "mega_abomasnow"]
    parser  = argparse.ArgumentParser(description="Dragapult ex interactive player")
    parser.add_argument("--opp",   default="mega_lucario", choices=choices)
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--log",   default="game_log.json")
    args = parser.parse_args()

    opp_mod = __import__(args.opp)

    print(f"対戦相手: {args.opp}  |  {args.games} ゲーム")
    print("ターン開始時に方針を自然文で入力してください\n")

    results = []
    for g in range(args.games):
        print(f"\n{'─' * W}")
        print(f"  ゲーム {g+1} / {args.games}")
        print(f"{'─' * W}")
        results.append(run_game(opp_mod.agent, opp_mod.my_deck))

    wins = results.count("WIN")
    print(f"\n最終結果: {wins}/{len(results)} 勝  ({100*wins//len(results) if results else 0}%)")

    with open(args.log, "w", encoding="utf-8") as f:
        json.dump(_log, f, ensure_ascii=False, indent=2)
    n_over = sum(1 for e in _log if e.get("overridden"))
    print(f"ログ保存: {args.log}  ({len(_log)} 決断 / 上書き {n_over} 回)")


if __name__ == "__main__":
    main()
