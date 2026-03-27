import ast
import configparser
import os
import select
import sys
import time
import traceback

import requests

from bot import Bot
from clients.tui_client import Config

TIMEOUT = 15


class ClientWithSaveAndLoad:
    def __init__(self, config=Config()):
        self.start_time = None
        self.session = None
        self.state = None
        self.running = True
        self.game_url = None
        self.config = config
        self.ai = config.ai
        self.bot = Bot(brain=self.ai)
        self.states = []
        self.delay = config.delay
        self.victory = 0
        self.time_out = 0
        self.log_win = True

    def load_config(self):
        config_parser = configparser.ConfigParser()
        user_home_dir = os.path.expanduser("~")
        config_file_name = os.path.join(user_home_dir, ".vindinium", "config")
        try:
            if os.path.isfile(config_file_name):
                config_parser.read(config_file_name)
                self.config.server_url = config_parser.get("game", "server_url")
                self.config.game_mode = config_parser.get("game", "game_mode")
                self.config.map_name = config_parser.get("game", "map_name")
                self.config.key = config_parser.get("game", "key")
                self.config.number_of_games = config_parser.getint(
                    "game", "number_of_games"
                )
                self.config.number_of_turns = config_parser.getint(
                    "game", "number_of_turns"
                )
        except (IOError, configparser.Error) as e:
            print("Error while loading config file", config_file_name, ":", e)
            quit(1)

    def save_config(self):
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
        except (IOError, configparser.Error) as e:
            print("Error  while saving config file", config_file_name, ":", e)
            quit(1)

    def load_game(self, game_file_name):
        self.states = []
        try:
            with open(game_file_name, "r") as game_file:
                for line in game_file.readlines():
                    if len(line.strip(chr(0)).strip()) > 0:
                        self.states.append(ast.literal_eval(line))
            self.state = self.states[0]
        except (IOError, IndexError) as e:
            print("Error while loading game file", game_file_name, ":", e)
            quit(1)

    def save_game(self):
        user_home_dir = os.path.expanduser("~")
        try:
            game_id = self.state["game"]["id"]
        except KeyError:
            try:
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
            self.pprint("Game saved: " + game_file_name)
        except IOError as e:
            print("Error  while saving game file", game_file_name, ":", e)

    def pprint(self, *args, **kwargs):
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

        # print("Event by {} : {}".format(self.ai.name, printable))

    def get_bot(self):
        return self.bot.clone_me()


class BasicClient(ClientWithSaveAndLoad):
    def __init__(self, config=Config()):
        super().__init__(config)

    def init(self):
        self.running = True
        self.game_url = None
        self.states = []
        self.state = None
        self.play()

    def play(self):
        self.victory = 0
        self.time_out = 0
        for i in range(self.config.number_of_games):
            # start a new game
            if self.bot.running:
                self.start_game()
                if not self.running:  # If game failed to start, skip to next game
                    continue

                gold = 0
                winner = ("Noone", -1)
                if self.bot.game and hasattr(self.bot.game, "heroes"):
                    for player in self.bot.game.heroes:
                        if int(player.gold) > gold:
                            winner = (player.name, player.bot_id)
                            gold = int(player.gold)
                    if winner[1] == self.bot.game.hero.bot_id:
                        self.victory += 1
                self.pprint("* " + winner[0] + " wins. ******************")
                summary = (str(i + 1) + "/" + str(self.config.number_of_games),)
                str(self.victory) + "/" + str(i + 1),
                str(self.time_out) + "/" + str(i + 1)
                self.pprint(summary)
                self.pprint(
                    "Game finished: "
                    + str(i + 1)
                    + "/"
                    + str(self.config.number_of_games)
                )

    def replay(self):
        """Replay last game"""
        # Restart with a new bot
        self.bot = Bot()
        for i in range(self.config.number_of_games):
            # start a new game
            if self.bot.running:
                self.restart_game()
                gold = 0
                winner = "Noone"
                for player in self.bot.game.heroes:
                    if int(player.gold) > gold:
                        winner = player.name
                        gold = int(player.gold)
                self.pprint("**** " + winner + " wins. ****")
                self.pprint(
                    "Game finished: "
                    + str(i + 1)
                    + "/"
                    + str(self.config.number_of_games)
                )

    def start_game(self):
        """Starts a game with all the required parameters"""
        self.running = True
        # Delete prévious game states
        self.states = []
        # Restart game with brand new bot
        self.bot = self.get_bot()
        # Default move is no move !
        direction = "Stay"
        # Create a requests session that will be used throughout the game
        self.pprint("Connecting...")
        self.session = requests.session()
        if self.config.game_mode == "arena":
            self.pprint("Waiting for other players to join...")
        try:
            # Get the initial state
            # May raise error if self.get_new_state() returns
            # no data or inconsistent data (network problem)
            self.state = self.get_new_game_state()
            if self.state is None:
                self.pprint(
                    "Failed to get game state. Please check the error messages above."
                )
                self.running = False
                return

            # Debug the state structure
            # self.pprint("Game state structure:")
            # self.pprint(f"Keys in state: {list(self.state.keys())}")
            # if 'game' in self.state:
            #     self.pprint(f"Keys in game: {list(self.state['game'].keys())}")
            # if 'hero' in self.state:
            #     self.pprint(f"Keys in hero: {list(self.state['hero'].keys())}")

            # Initialize the bot's game state
            self.bot.process_game(self.state)

            self.states.append(self.state)
            try:
                self.pprint("Playing at: " + self.state["viewUrl"])
            except KeyError as e:
                self.pprint(f"Error accessing viewUrl: {e}")
                self.pprint("State structure:", self.state)
                self.running = False
                return
        except (KeyError, TypeError) as e:
            # We can not play a game without a state
            self.pprint("Error: Please verify your settings.")
            self.pprint("Settings:", self.config.__dict__)
            self.pprint("Error details:", str(e))
            self.running = False
            return
        for i in range(self.config.number_of_turns + 1):
            if self.running:
                # Choose a move
                self.start_time = time.time()
                try:
                    while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                        line = sys.stdin.read(1)
                        if line.strip() == "q":
                            self.running = False
                            self.bot.running = False
                            break
                        elif line.strip() == "p":
                            self.gui.pause()
                        elif line.strip() == "s":
                            self.save_game()
                    if self.bot.running:
                        direction = self.bot.move(self.state)
                except Exception as e:
                    # Super error trap !
                    if self.log_win:
                        print(f"Caught an error: {e}")
                        print("\n--- Printing traceback with traceback.print_exc() ---")
                        traceback.print_exc()
                        self.pprint("Error at client.start_game:", str(e))
                    self.running = False
                    return
                if not self.is_game_over():
                    # Send the move and receive the updated game state
                    self.game_url = self.state["playUrl"]
                    self.state = self.send_move(direction)
                    self.states.append(self.state)
        # Clean up the session
        self.session.close()

    def get_new_game_state(self):
        if self.config.game_mode == "training":
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
        try:
            full_url = self.config.server_url + api_endpoint
            self.pprint(f"Connecting to: {full_url}")
            # self.pprint(f"With parameters: {params}")
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            r = self.session.post(full_url, params, headers=headers, timeout=10 * 60)
            # self.pprint(f"Response status code: {r.status_code}")
            # self.pprint(f"Response headers: {dict(r.headers)}")
            if r.status_code == 200:
                try:
                    response_json = r.json()
                    self.pprint("Successfully parsed JSON response")
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
        try:
            return self.state["game"]["finished"]
        except (TypeError, KeyError):
            return True

    def send_move(self, direction):
        try:
            response = self.session.post(
                self.game_url, {"dir": direction}, timeout=TIMEOUT
            )
            if response.status_code == 200:
                return response.json()
            else:
                self.pprint(
                    "Error HTTP ", str(response.status_code), ": ", response.text
                )
                self.time_out += 1
                self.running = False
                return {"game": {"finished": True}}
        except requests.exceptions.RequestException as e:
            self.pprint("Error at client.move;", str(e))
            self.running = False
            return {"game": {"finished": True}}


if __name__ == "__main__":
    API_KEY = "s9sp71r9"  # Replace with your actual
    URL = "http://localhost"  # Replace with your actual server URL
    config = Config(
        key=API_KEY,
        server_url=URL,
        game_mode="training",
        number_of_games=1,
        number_of_turns=10,
        map_name="m1",
        delay=0.1,
    )
    client = BasicClient(config)
    client.play()
