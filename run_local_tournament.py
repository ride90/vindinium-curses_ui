import gc
import threading
import sys

# Configure garbage collection
gc.set_threshold(700, 10, 5)  # Increase thresholds to reduce collection frequency
gc.disable()  # Disable automatic garbage collection during tournament

from clients.basic_client import BasicClient
from clients.tui_client import Config
from models import (
    adaptive_lookahead_ai,
    heuristic_ai,
    tactical_ai_v2,
    tactical_ai_v4,
    risk_reward_ai,
    tactical_ai_v3,
)

# Local tournament for Vindinium AIs
# Configuration for the local tournament

ai_configs = [
    {"ai": tactical_ai_v2.AI("tactical_v2", "q5nljjw0")},
    {"ai": tactical_ai_v3.AI("tactical_v3", "2lkw2t8g")},
    {"ai": risk_reward_ai.AI("risk_reward_v2", "h3q5f9or")},
    # {"ai": tactical_ai_v4.AI("tactical_v4", "e4ynvrte")},
    {"ai": heuristic_ai.AI("heuristic1", "gx2wtjfq")},
]

base_config = dict(
    number_of_games=500,
    number_of_turns=200,
    map_name="m6",
    game_mode="arena",
    server_url="http://localhost",
    delay=0,  # Map name: "m1", "m2", "m3", "m4", "m5", or "m6"
)


def wait_for_enter():
    """Simple cross-platform function to wait for Enter key press"""
    print("Press Enter to launch the tournament...", end="", flush=True)
    sys.stdin.readline()
    print()  # New line after Enter


if __name__ == "__main__":
    try:
        client_configs = [
            Config.from_dict({**base_config, **ai_config}) for ai_config in ai_configs
        ]
        clients = [BasicClient(config) for config in client_configs]

        wait_for_enter()

        threads = []
        for c in clients:
            t = threading.Thread(target=c.play)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        print("Tournament completed.")
    finally:
        gc.enable()  # Re-enable garbage collection after tournament
