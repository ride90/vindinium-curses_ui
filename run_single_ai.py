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

ai_config = {"ai": tactical_ai_v2.AI("CassiusAI", "65xgj0lw")}


base_config = dict(
    number_of_games=1,
    number_of_turns=4,
    map_name="m6",
    game_mode="training",
    server_url="https://vindinium.josefelixh.net",
    delay=0,  # Map name: "m1", "m2", "m3", "m4", "m5", or "m6"
)


def wait_for_enter():
    """Simple cross-platform function to wait for Enter key press"""
    print("Press Enter to launch the tournament...", end="", flush=True)
    sys.stdin.readline()
    print()  # New line after Enter


if __name__ == "__main__":
    try:
        client_config = Config.from_dict({**base_config, **ai_config})

        client = BasicClient(client_config)

        wait_for_enter()

        threads = []
        client.play()

        print("Tournament completed.")
    finally:
        gc.enable()  # Re-enable garbage collection after tournament
