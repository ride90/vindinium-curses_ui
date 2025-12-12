#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Manual Client for Vindinium Game

This script allows you to configure game parameters directly in code
without using the interactive UI. Simply edit the configuration dictionaries
below and run the script to start playing.

Usage: python manual_client.py
"""

import requests
from bot import Bot
import sys
import select
import time
import os
import configparser
import ast

# =============================================================================
# CONFIGURATION SECTION - EDIT THESE DICTIONARIES TO CONFIGURE YOUR GAME
# =============================================================================

# Game Mode Configuration
# Choose either "training" or "arena"
GAME_CONFIG = {
    "game_mode": "training",  # "training" or "arena"
    "server_url": "http://vindinium.org",  # Server URL
    "key": "your_api_key_here",  # Your 8-character API key
}

# Training Mode Configuration (only used if game_mode = "training")
TRAINING_CONFIG = {
    "number_of_turns": 300,  # Number of turns for the game
    "map_name": "m3",  # Map name: "m1", "m2", "m3", "m4", "m5", or "m6"
}

# Arena Mode Configuration (only used if game_mode = "arena")
ARENA_CONFIG = {
    "number_of_games": 1,  # Number of games to play consecutively
}

# General Settings
GENERAL_CONFIG = {
    "save_config_to_file": False,  # Whether to save config to ~/.vindinium/config
    "auto_save_games": True,  # Whether to automatically save games
    "delay_between_moves": 0.5,  # Delay in seconds between moves (for display)
}

# =============================================================================
# END OF CONFIGURATION SECTION
# =============================================================================

TIMEOUT = 15


class Config:
    def __init__(
        self,
        game_mode="training",
        server_url="http://vindinium.org",
        number_of_games=1,
        number_of_turns=300,
        map_name="m3",
        key=None,
    ):
        self.game_mode = game_mode
        self.number_of_games = number_of_games
        self.number_of_turns = number_of_turns
        self.map_name = map_name
        self.server_url = server_url
        self.key = key


class ManualClient:
    def __init__(self):
        self.start_time = None
        self.gui = None
        self.session = None
        self.state = None
        self.running = True
        self.game_url = None
        self.config = self._create_config_from_dictionaries()
        self.bot = Bot()  # Our bot
        self.states = []
        self.delay = GENERAL_CONFIG.get("delay_between_moves", 0.5)
        self.victory = 0
        self.time_out = 0

    def _create_config_from_dictionaries(self):
        """Create a Config object from the configuration dictionaries"""
        config = Config()

        # Set basic configuration
        config.game_mode = GAME_CONFIG["game_mode"]
        config.server_url = GAME_CONFIG["server_url"]
        config.key = GAME_CONFIG["key"]

        # Set mode-specific configuration
        if config.game_mode == "training":
            config.number_of_games = 1
            config.number_of_turns = TRAINING_CONFIG["number_of_turns"]
            config.map_name = TRAINING_CONFIG["map_name"]
        elif config.game_mode == "arena":
            config.number_of_games = ARENA_CONFIG["number_of_games"]
            config.number_of_turns = 300  # Fixed for arena mode
            config.map_name = ""  # Not used in arena mode

        return config

    def _validate_config(self):
        """Validate the configuration before starting"""
        errors = []

        # Validate game mode
        if GAME_CONFIG["game_mode"] not in ["training", "arena"]:
            errors.append("game_mode must be either 'training' or 'arena'")

        # Validate API key format (should be 8 alphanumeric characters)
        key = GAME_CONFIG["key"]
        if not key or len(key) != 8 or not key.isalnum():
            errors.append("API key must be exactly 8 alphanumeric characters")

        # Validate server URL
        if not GAME_CONFIG["server_url"].startswith("http"):
            errors.append("server_url must be a valid HTTP/HTTPS URL")

        # Validate training mode specific settings
        if GAME_CONFIG["game_mode"] == "training":
            if TRAINING_CONFIG["number_of_turns"] <= 0:
                errors.append("number_of_turns must be greater than 0")
            if TRAINING_CONFIG["map_name"] not in ["m1", "m2", "m3", "m4", "m5", "m6"]:
                errors.append("map_name must be one of: m1, m2, m3, m4, m5, m6")

        # Validate arena mode specific settings
        if GAME_CONFIG["game_mode"] == "arena":
            if ARENA_CONFIG["number_of_games"] <= 0:
                errors.append("number_of_games must be greater than 0")

        return errors

    def pprint(self, *args, **kwargs):
        """Print function for logging - simplified version without GUI"""
        printable = ""
        for arg in args:
            printable = printable + str(arg) + " "
        if kwargs and len(kwargs):
            a = 1
            coma = ""
            printable = printable + "["
            for k, v in kwargs.items():
                if 1 < a < len(kwargs):
                    coma = ", "
                else:
                    coma = "]"
                printable = printable + str(k) + ": " + str(v) + coma
                a = a + 1
        print(printable)

    def save_config(self):
        """Save config to file in ~/.vindinium/config"""
        if not GENERAL_CONFIG.get("save_config_to_file", False):
            return

        config_parser = configparser.ConfigParser()
        user_home_dir = os.path.expanduser("~")
        config_file_name = os.path.join(user_home_dir, ".vindinium", "config")
        try:
            if not os.path.isdir(os.path.join(user_home_dir, ".vindinium")):
                os.makedirs(os.path.join(user_home_dir, ".vindinium"))
            config_parser.add_section("game")
            with open(config_file_name, "w") as config_file:
                for key, value in self.config.__dict__.items():
                    config_parser.set("game", key, str(value))
                config_parser.write(config_file)
            self.pprint(f"Configuration saved to {config_file_name}")
        except (IOError, configparser.Error) as e:
            self.pprint("Error while saving config file", config_file_name, ":", e)

    def save_game(self):
        """Save game to file in ~/.vindinium/save/<game ID>"""
        if not GENERAL_CONFIG.get("auto_save_games", True):
            return

        user_home_dir = os.path.expanduser("~")
        try:
            # Get game_id from game state
            game_id = self.state["game"]["id"]
        except KeyError:
            try:
                # State has not been downloaded
                # Try to get game_id from last state saved if any
                game_id = self.states[0]["game"]["id"]
            except IndexError:
                self.pprint("No states available for this game, unable to save game.")
                return
        game_file_name = os.path.join(user_home_dir, ".vindinium", "save", game_id)
        try:
            if not os.path.isdir(os.path.join(user_home_dir, ".vindinium", "save")):
                os.makedirs(os.path.join(user_home_dir, ".vindinium", "save"))
            with open(game_file_name, "w") as game_file:
                for state in self.states:
                    game_file.write(str(state) + "\n")
            self.pprint("Game saved:", game_file_name)
        except IOError as e:
            self.pprint("Error while saving game file", game_file_name, ":", e)

    def play_games(self):
        """Play all configured games"""
        self.pprint("Starting game with configuration:")
        self.pprint(f"Game Mode: {self.config.game_mode}")
        self.pprint(f"Server URL: {self.config.server_url}")
        if self.config.game_mode == "training":
            self.pprint(f"Number of turns: {self.config.number_of_turns}")
            self.pprint(f"Map: {self.config.map_name}")
        else:
            self.pprint(f"Number of games: {self.config.number_of_games}")
        self.pprint()

        self.victory = 0
        self.time_out = 0

        for i in range(self.config.number_of_games):
            self.pprint(f"Starting game {i+1}/{self.config.number_of_games}")
            if self.bot.running:
                self.start_game()
                if not self.running:  # If game failed to start, skip to next game
                    continue

                # Determine winner
                gold = 0
                winner = ("No one", -1)
                if self.bot.game and hasattr(self.bot.game, "heroes"):
                    for player in self.bot.game.heroes:
                        if int(player.gold) > gold:
                            winner = (player.name, player.bot_id)
                            gold = int(player.gold)
                    if winner[1] == self.bot.game.hero.bot_id:
                        self.victory += 1

                self.pprint(f"*** {winner[0]} wins! ***")
                self.pprint(
                    f"Games summary - Played: {i+1}/{self.config.number_of_games}, Won: {self.victory}/{i+1}, Timed out: {self.time_out}/{i+1}"
                )
                self.pprint(f"Game finished: {i+1}/{self.config.number_of_games}")
                self.pprint()

    def start_game(self):
        """Starts a game with all the required parameters"""
        self.running = True
        # Delete previous game states
        self.states = []
        # Restart game with brand new bot
        self.bot = Bot()
        # Default move is no move!
        direction = "Stay"
        # Create a requests session that will be used throughout the game
        self.pprint("Connecting...")
        self.session = requests.session()
        if self.config.game_mode == "arena":
            self.pprint("Waiting for other players to join...")
        try:
            # Get the initial state
            self.state = self.get_new_game_state()
            if self.state is None:
                self.pprint(
                    "Failed to get game state. Please check the error messages above."
                )
                self.running = False
                return

            # Initialize the bot's game state
            self.bot.process_game(self.state)
            self.states.append(self.state)

            try:
                self.pprint("Playing at:", self.state["viewUrl"])
            except KeyError as e:
                self.pprint(f"Error accessing viewUrl: {e}")
                self.pprint("State structure:", self.state)
                self.running = False
                return
        except (KeyError, TypeError) as e:
            # We cannot play a game without a state
            self.pprint("Error: Please verify your settings.")
            self.pprint("Settings:", self.config.__dict__)
            self.pprint("Error details:", str(e))
            self.running = False
            return

        # Game loop
        for i in range(self.config.number_of_turns + 1):
            if self.running:
                # Choose a move
                self.start_time = time.time()
                try:
                    # Check for keyboard input (q to quit, s to save)
                    while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                        line = sys.stdin.read(1)
                        if line.strip() == "q":
                            self.running = False
                            self.bot.running = False
                            self.pprint("Game interrupted by user")
                            break
                        elif line.strip() == "s":
                            self.save_game()

                    if self.bot.running:
                        direction = self.bot.move(self.state)
                        self.display_game_info()

                except Exception as e:
                    self.pprint("Error during game:", str(e))
                    self.running = False
                    return

                if not self.is_game_over():
                    # Send the move and receive the updated game state
                    self.game_url = self.state["playUrl"]
                    self.state = self.send_move(direction)
                    self.states.append(self.state)
                else:
                    break

        # Clean up the session
        self.session.close()

        # Auto-save game if enabled
        if GENERAL_CONFIG.get("auto_save_games", True):
            self.save_game()

    def display_game_info(self):
        """Display simplified game information (console version)"""
        if hasattr(self.bot, "game") and self.bot.game:
            game = self.bot.game
            hero = game.hero

            turn = game.turn // 4 if hasattr(game, "turn") else 0
            max_turns = game.max_turns // 4 if hasattr(game, "max_turns") else 0

            elapsed = round(time.time() - self.start_time, 3) if self.start_time else 0

            # Display key game information
            info = (
                f"Turn {turn}/{max_turns} | "
                f"Pos: {hero.pos} | "
                f"Life: {hero.life} | "
                f"Gold: {hero.gold} | "
                f"Mines: {hero.mine_count} | "
                f"Move: {self.bot.hero_move if hasattr(self.bot, 'hero_move') else 'Stay'} | "
                f"Time: {elapsed}s"
            )
            self.pprint(info)

            # Add a small delay to make the output readable
            time.sleep(self.delay)

    def get_new_game_state(self):
        """Get a JSON from the server containing the current state of the game"""
        if self.config.game_mode == "training":
            # Don't pass the 'map' parameter if no map has been selected
            if len(self.config.map_name) > 0:
                params = {
                    "key": self.config.key,
                    "turns": self.config.number_of_turns,
                    "map": self.config.map_name,
                }
            else:
                params = {"key": self.config.key, "turns": self.config.number_of_turns}
            api_endpoint = "/api/training"
        elif self.config.game_mode == "arena":
            params = {"key": self.config.key}
            api_endpoint = "/api/arena"
        else:
            raise Exception("Unknown game mode")

        # Wait for 10 minutes
        try:
            full_url = self.config.server_url + api_endpoint
            self.pprint(f"Connecting to: {full_url}")
            self.pprint(f"With parameters: {params}")

            # Set headers to expect JSON response
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            r = self.session.post(full_url, params, headers=headers, timeout=10 * 60)
            self.pprint(f"Response status code: {r.status_code}")

            if r.status_code == 200:
                try:
                    response_json = r.json()
                    self.pprint("Successfully connected and got game state")
                    return response_json
                except ValueError as e:
                    self.pprint("Error parsing JSON response:")
                    self.pprint(r.text[:200] + "..." if len(r.text) > 200 else r.text)
                    self.running = False
                    return None
            else:
                self.pprint(f"Error when creating the game: HTTP {r.status_code}")
                self.pprint("Server response:")
                self.pprint(r.text[:200] + "..." if len(r.text) > 200 else r.text)
                self.pprint("\nPlease check:")
                self.pprint("1. The server URL is correct")
                self.pprint("2. The server is running and accessible")
                self.pprint("3. Your API key is valid")
                self.running = False
                return None
        except requests.ConnectionError as e:
            self.pprint("Connection error when creating the game:")
            self.pprint(str(e))
            self.pprint("\nPlease check:")
            self.pprint("1. The server URL is correct")
            self.pprint("2. The server is running and accessible")
            self.pprint("3. Your internet connection is working")
            self.running = False
            return None
        except requests.Timeout as e:
            self.pprint("Timeout when creating the game:")
            self.pprint(str(e))
            self.pprint("\nThe server took too long to respond. Please try again.")
            self.running = False
            return None
        except Exception as e:
            self.pprint("Unexpected error when creating the game:")
            self.pprint(str(e))
            self.running = False
            return None

    def is_game_over(self):
        """Return True if game defined by state is over"""
        try:
            return self.state["game"]["finished"]
        except (TypeError, KeyError):
            return True

    def send_move(self, direction):
        """Send a move to the server
        Moves can be one of: 'Stay', 'North', 'South', 'East', 'West'"""
        try:
            response = self.session.post(
                self.game_url, {"dir": direction}, timeout=TIMEOUT
            )
            if response.status_code == 200:
                return response.json()
            else:
                self.pprint("Error HTTP", str(response.status_code), ":", response.text)
                self.time_out += 1
                self.running = False
                return {"game": {"finished": True}}
        except requests.exceptions.RequestException as e:
            self.pprint("Error sending move:", str(e))
            self.running = False
            return {"game": {"finished": True}}

    def run(self):
        """Main entry point to run the manual client"""
        print("========================================")
        print("Vindinium Manual Client")
        print("========================================")
        print()

        # Validate configuration
        errors = self._validate_config()
        if errors:
            print("Configuration errors found:")
            for error in errors:
                print(f"  - {error}")
            print()
            print(
                "Please fix the configuration in the CONFIGURATION SECTION at the top of this file."
            )
            return 1

        print("Configuration validated successfully!")
        print()

        # Save configuration if requested
        if GENERAL_CONFIG.get("save_config_to_file", False):
            self.save_config()

        # Start playing
        try:
            self.play_games()
            print("\n========================================")
            print("All games completed!")
            print(
                f"Final results: {self.victory} victories out of {self.config.number_of_games} games"
            )
            print("========================================")
            return 0
        except KeyboardInterrupt:
            print("\n\nGame interrupted by user (Ctrl+C)")
            return 1
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            return 1


if __name__ == "__main__":
    print("Starting Vindinium Manual Client...")
    print("Press 'q' during game to quit, 's' to save game state")
    print("Press Ctrl+C to interrupt at any time")
    print()

    client = ManualClient()
    exit_code = client.run()
    sys.exit(exit_code)
