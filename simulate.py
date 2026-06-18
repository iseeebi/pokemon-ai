"""
シミュレーション実行スクリプト（プロジェクトルートから実行）

Usage:
  python simulate.py festival_lead               # current vs 4 opponents (100 games)
  python simulate.py festival_lead --compare     # 直近アーカイブ vs current + 参考値テーブル
  python simulate.py festival_lead --games 20    # 試合数を変更
  python simulate.py festival_lead --verbose     # 各試合の勝敗を表示
"""
import sys
import os
import json
import argparse
import glob
import importlib
import re
from collections import Counter

_ROOT = os.path.dirname(os.path.abspath(__file__))


def setup_paths(agent_name: str) -> str:
    """sys.path と cwd をエージェントディレクトリ用に設定し、パスを返す。"""
    agent_dir = os.path.join(_ROOT, "agents", agent_name)
    if not os.path.isdir(agent_dir):
        print(f"Error: agents/{agent_name}/ not found", file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, os.path.join(_ROOT, "submission"))  # cg engine
    sys.path.insert(0, agent_dir)                          # main.py + v*_agent.py
    sys.path.insert(0, os.path.join(_ROOT, "opponents"))   # 対戦相手エージェント
    os.chdir(agent_dir)                                    # deck.csv 読み込み用
    return agent_dir


def load_opponents():
    import dragapult_ex, iono, mega_abomasnow, mega_lucario
    return [
        ("Dragapult ex",    dragapult_ex.agent,    dragapult_ex.my_deck),
        ("Iono's Deck",     iono.agent,            iono.my_deck),
        ("Mega Abomasnow",  mega_abomasnow.agent,  mega_abomasnow.my_deck),
        ("Mega Lucario ex", mega_lucario.agent,    mega_lucario.my_deck),
    ]


def discover_archived(agent_dir: str):
    """v*_agent.py を番号順に返す。"""
    versions = []
    for path in sorted(
        glob.glob(os.path.join(agent_dir, "v*_agent.py")),
        key=lambda p: int(re.search(r"v(\d+)_agent\.py", os.path.basename(p)).group(1)),
    ):
        name = os.path.splitext(os.path.basename(path))[0]
        ver_label = re.match(r"(v\d+)_agent", name).group(1)
        mod = importlib.import_module(name)
        versions.append((ver_label, mod.agent, mod.my_deck))
    return versions


def load_results(agent_dir: str) -> dict:
    path = os.path.join(agent_dir, "results.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_results(agent_dir: str, data: dict):
    path = os.path.join(agent_dir, "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------

def run_game(agent0, agent1, deck0, deck1) -> int:
    from cg.game import battle_start, battle_select, battle_finish
    obs_dict, _ = battle_start(deck0, deck1)
    if obs_dict is None:
        return -1
    agents = [agent0, agent1]
    for _ in range(5000):
        current = obs_dict.get("current")
        if current and current.get("result", -1) != -1:
            battle_finish()
            return current["result"]
        player_idx = current["yourIndex"] if current else 0
        try:
            action   = agents[player_idx](obs_dict)
            obs_dict = battle_select(action)
        except Exception as e:
            print(f"  [error] player={player_idx}: {e}", file=sys.stderr)
            battle_finish()
            return -1
    battle_finish()
    return -1


def run_series(my_agent, my_deck, opp_agent, opp_deck, n, verbose, label):
    results = Counter()
    for i in range(n):
        if i % 2 == 0:
            result = run_game(my_agent, opp_agent, my_deck, opp_deck)
            win = (result == 0)
        else:
            result = run_game(opp_agent, my_agent, opp_deck, my_deck)
            win = (result == 1)

        if result == -1:
            results["draw"] += 1; outcome = "DRAW"
        elif win:
            results["win"]  += 1; outcome = "WIN"
        else:
            results["lose"] += 1; outcome = "LOSE"

        if verbose:
            print(f"  [{label}] game {i+1:3d}: {outcome}")

    return results["win"], results["lose"], results["draw"]


# ---------------------------------------------------------------------------

def run_single(agent_dir, args):
    import main as agent_module
    opponents = load_opponents()
    opp_names = [n for n, _, _ in opponents]
    col_w = max(len(n) for n in opp_names)

    print(f"[{args.agent}] current  vs  4 opponents  ({args.games} games each)")
    sep = "-" * (col_w + 28)
    print(sep)
    print(f"{'Opponent':<{col_w}}  {'W':>4}  {'L':>4}  {'D':>4}  {'Win%':>6}")
    print(sep)

    total_w = total_l = total_d = 0
    for name, opp_agent, opp_deck in opponents:
        w, l, d = run_series(agent_module.agent, agent_module.my_deck,
                             opp_agent, opp_deck, args.games, args.verbose, name)
        total_w += w; total_l += l; total_d += d
        print(f"{name:<{col_w}}  {w:>4}  {l:>4}  {d:>4}  {w/args.games*100:>5.1f}%")

    total = total_w + total_l + total_d
    print(sep)
    pct = total_w / total * 100 if total else 0.0
    print(f"{'TOTAL':<{col_w}}  {total_w:>4}  {total_l:>4}  {total_d:>4}  {pct:>5.1f}%")


def run_compare(agent_dir, args):
    import main as agent_module
    archived  = discover_archived(agent_dir)
    opponents = load_opponents()
    opp_names = [n for n, _, _ in opponents]
    cache     = load_results(agent_dir)
    col_w = 10

    if archived:
        ref_versions = archived[:-1]
        sim_versions = [archived[-1],
                        ("current", agent_module.agent, agent_module.my_deck)]
    else:
        ref_versions = []
        sim_versions = [("current", agent_module.agent, agent_module.my_deck)]

    sim_label = " vs ".join(v for v, _, _ in sim_versions)
    print(f"[{args.agent}] Simulating: {sim_label}  ({args.games} games each)")
    if ref_versions:
        ref_label = ", ".join(v for v, _, _ in ref_versions)
        print(f"Reference (cached): {ref_label}")
    print()

    header = f"{'Version':<12}" + "".join(f"  {n[:col_w]:>{col_w}}" for n in opp_names) + f"  {'TOTAL':>6}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    # キャッシュ行
    for ver_name, _, _ in ref_versions:
        if ver_name in cache:
            d = cache[ver_name]
            pcts = [d.get(n, float("nan")) for n in opp_names]
            total_pct = d.get("TOTAL", float("nan"))
            label = f"{ver_name} *"
        else:
            pcts = [float("nan")] * len(opp_names)
            total_pct = float("nan")
            label = f"{ver_name} ?"
        cells = "".join(f"  {p:>{col_w}.1f}%" if p == p else f"  {'N/A':>{col_w}}" for p in pcts)
        t = f"{total_pct:>5.1f}%" if total_pct == total_pct else "  N/A"
        print(f"{label:<12}{cells}  {t}")

    # シミュレーション行
    new_cache = dict(cache)
    for ver_name, my_agent, my_deck in sim_versions:
        row_pcts = []
        total_w = total_games = 0
        for opp_name, opp_agent, opp_deck in opponents:
            w, l, d = run_series(my_agent, my_deck, opp_agent, opp_deck,
                                 args.games, args.verbose, f"{ver_name} vs {opp_name}")
            pct = w / args.games * 100
            row_pcts.append(pct)
            total_w += w; total_games += args.games

        total_pct = total_w / total_games * 100
        cells = "".join(f"  {p:>{col_w}.1f}%" for p in row_pcts)
        print(f"{ver_name:<12}{cells}  {total_pct:>5.1f}%")

        if ver_name != "current" and args.games >= 50:
            new_cache[ver_name] = {opp_names[i]: row_pcts[i] for i in range(len(opp_names))}
            new_cache[ver_name]["TOTAL"] = total_pct

    print(sep)
    if ref_versions:
        print("* cached result")

    if any(v != "current" and args.games >= 50 for v, _, _ in sim_versions):
        save_results(agent_dir, new_cache)


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("agent",   help="agents/ 以下のディレクトリ名（例: festival_lead）")
    parser.add_argument("--compare", action="store_true",
                        help="直近アーカイブ vs current を比較し古いバージョンは参考値表示")
    parser.add_argument("--games",   type=int, default=100)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    agent_dir = setup_paths(args.agent)

    if args.compare:
        run_compare(agent_dir, args)
    else:
        run_single(agent_dir, args)


if __name__ == "__main__":
    main()
