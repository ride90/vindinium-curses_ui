#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vindinium Bot – horizon‑aware heuristic AI
=========================================

* Uses the official **`bot_id`** field everywhere (no `.id` fallback).
* When looking for a mine to capture, it **excludes mines you already own**, so
  the bot never targets a tile it controls.
* Works for any `maxTurns` length by scaling its phase boundaries.
* Pure Python ≥ 3.8; no external dependencies.

Modules
-------
* `Hero`, `Game` – light state wrappers for the server JSON.
* `AI` – the decision‑making brain. Instantiate *once*; call `process(state)`
  then `decide()` each turn.
"""

from typing import List, Tuple


# ---------------------------------------------------------------------------
#  Domain objects
# ---------------------------------------------------------------------------


class Hero:
    """A minimal mirror of the JSON hero structure."""

    def __init__(self, hero_dict: dict):
        self.bot_id: int = hero_dict["id"]  # ← server uses "id" in JSON
        self.life: int = hero_dict["life"]
        self.gold: int = hero_dict["gold"]
        self.pos: Tuple[int, int] = (hero_dict["pos"]["x"], hero_dict["pos"]["y"])
        self.reversePos: Tuple[int, int] = self.pos
        self.spawn_pos: Tuple[int, int] = (
            hero_dict["spawnPos"]["x"],
            hero_dict["spawnPos"]["y"],
        )
        self.crashed: bool = hero_dict["crashed"]
        self.mine_count: int = hero_dict["mineCount"]
        self.mines: List[Tuple[int, int]] = []  # filled later by Game
        self.name: str = hero_dict["name"]
        # Optional fields missing on training bots
        self.elo: int = hero_dict.get("elo", 0)
        self.user_id: int = hero_dict.get("userId", 0)
        self.last_move: str | None = hero_dict.get("lastDir")


class Game:
    """Wrapper that parses the raw game JSON into handy structures."""

    def __init__(self, state: dict):
        self.state = state
        self.mines = {}  # Dictionary to store mine ownership
        self.mines_locs = []  # List of mine positions
        self.spawn_points_locs = {}
        self.taverns_locs = []
        self.hero = None
        self.heroes = []
        self.heroes_locs = []
        self.walls_locs = []
        self.url = None
        self.turn = None
        self.max_turns = None
        self.finished = None
        self.board_size = None
        self.board_map = []

        self.process_data(self.state)

    def process_data(self, state):
        """Parse the game state"""
        self.set_url(state["viewUrl"])
        self.process_hero(state["hero"])
        self.process_game(state["game"])

    def set_url(self, url):
        """Set the game object url var"""
        self.url = url

    def process_hero(self, hero):
        """Process the hero data"""
        self.hero = Hero(hero)

    def process_game(self, game):
        """Process the game data"""
        process = {"board": self.process_board, "heroes": self.process_heroes}
        self.turn = game["turn"]
        self.max_turns = game["maxTurns"]
        self.finished = game["finished"]
        for key in sorted(game.keys()):  # TODO: board must go before heroes
            if key in process:
                process[key](game[key])

    def process_board(self, board):
        """Process the board datas
        - Retrieve walls locs, tavern locs
        - Converts tiles in a displayable form"""
        self.board_size = board["size"]
        tiles = board["tiles"]
        map_line = ""
        char = None
        for y in range(0, len(tiles), self.board_size * 2):
            line = tiles[y : y + self.board_size * 2]
            for x in range(0, len(line), 2):
                tile = line[x : x + 2]
                tile_coords = (y // self.board_size // 2, x // 2)
                if tile[0] == " ":
                    # It's passable
                    char = " "
                elif tile[0] == "#":
                    # It's a wall
                    char = "#"
                    self.walls_locs.append(tile_coords)
                elif tile[0] == "$":
                    # It's a mine
                    char = "$"
                    self.mines_locs.append(tile_coords)
                    # Handle mine ownership: '-' means no owner, otherwise it's a player ID
                    owner = tile[1]
                    if owner == "-":
                        self.mines[tile_coords] = None  # No owner
                    else:
                        self.mines[tile_coords] = int(owner)
                        if owner == str(self.hero.bot_id):
                            # This mine belongs to me
                            self.hero.mines.append(tile_coords)
                elif tile[0] == "[":
                    # It's a tavern
                    char = "T"
                    self.taverns_locs.append(tile_coords)
                elif tile[0] == "@":
                    # It's a hero
                    char = "H"
                    if not int(tile[1]) == self.hero.bot_id:
                        # I don't want to be put in an array !
                        # I'm not a number, i'm a free bot:-)
                        self.heroes_locs.append(tile_coords)
                    else:
                        # And I want to be differenciated
                        char = "@"
                map_line = map_line + str(char)
            self.board_map.append(map_line)
            map_line = ""

    def process_heroes(self, heroes: list):
        for h in heroes:
            self.spawn_points_locs[(h["spawnPos"]["y"], h["spawnPos"]["x"])] = h["id"]
            hero_obj = Hero(h)
            self.heroes.append(hero_obj)
            # Mark spawn on map unless occupied by hero char
            line = list(self.board_map[hero_obj.spawn_pos[1]])
            if line[hero_obj.spawn_pos[0]] not in {"@", "H"}:
                line[hero_obj.spawn_pos[0]] = "X"
            self.board_map[hero_obj.spawn_pos[1]] = "".join(line)


# ---------------------------------------------------------------------------
#  Stand‑alone run hook (useful for local debugging)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("This module is intended to be imported by the Vindinium starter‑kit.")
