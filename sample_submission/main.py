import os
import random

from cg.api import Observation, to_observation_class

def read_deck_csv() -> list[int]:
    file_path = "deck.csv"

    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path

    deck = []

    with open(file_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line == "":
                continue
            deck.append(int(line))

    # 強制チェック
    if len(deck) != 60:
        raise ValueError(f"Deck size invalid: {len(deck)}")

    return deck

def agent(obs_dict: dict) -> list[int]:
    """Implement Your Pokémon Trading Card Game Agent.

    Each element in the returned list must be >= 0 and < len(obs.select.option).
    The list length must be between obs.select.minCount and obs.select.maxCount (inclusive), with no duplicate elements.
    
    Returns:
        list[int]: A list of option index.
    """
    obs: Observation = to_observation_class(obs_dict)
    if obs.select == None:
        # In the initial selection, the obs.select is None, and it is necessary to return the deck.
        # The deck is a list of 60 card IDs.
        # The deck must comply with the Pokémon Trading Card Game rules.
        return read_deck_csv()
    
    return random.sample(list(range(len(obs.select.option))), obs.select.maxCount)  # select randomly
