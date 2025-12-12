from abc import ABC, abstractmethod
from collections import deque
from enum import Enum
import os
import csv
from datetime import datetime

from game import Game


class MapElements(str, Enum):
    OWNED_MINE = "O"
    HERO = "@"
    MINE = "$"
    ENEMY = "H"
    TAVERN = "T"


class Directions(str, Enum):
    NORTH = "North"
    SOUTH = "South"
    EAST = "East"
    WEST = "West"
    STAY = "Stay"

    @staticmethod
    def get_direction(start_pos, next):
        start_row, start_col = start_pos
        next_row, next_col = next

        dr = next_row - start_row
        dc = next_col - start_col

        if dr == -1 and dc == 0:
            return "North"
        elif dr == 1 and dc == 0:
            return "South"
        elif dr == 0 and dc == 1:
            return "East"
        elif dr == 0 and dc == -1:
            return "West"
        elif dr == 0 and dc == 0:
            return "Stay"
        else:
            # This handles diagonal moves or jumps of more than one cell
            return "Stay"


class Actions(str, Enum):
    NEAREST_TAVERN = "NEAREST_TAVERN"
    OPPORTUNISTIC_TAVERN = "OPPORTUNISTIC_TAVERN"
    ENDGAME_TAVERN = "ENDGAME_TAVERN"
    TAKE_NEAREST_MINE = "TAKE_NEAREST_MINE"
    ATTACK_NEAREST = "ATTACK_NEAREST"
    ATTACK_RICHEST = "ATTACK_RICHEST"
    ATTACK_WEAKEST = "ATTACK_WEAKEST"
    SUICIDE = "SUICIDE"
    WAIT = "WAIT"
    DEFEND_MINE = "DEFEND_MINE"
    RUN = "RUN"
    TWO_STOP_ATTACK = "TWO_STOP_ATTACK"
    TWO_STOP_MINE = "TWO_STOP_MINE"
    EXPLORE = "EXPLORE"


class AIBase(ABC):
    def __init__(self, name: str = "UnknownAIName", key: str = "UnknownKey"):
        self.game: Game | None = None
        self.prev_life: int | None = None
        self.key = key  # Unique identifier for the AI instanceer for the AI instance
        self.name = name

    def clone_me(self):
        """Create a clone of the AI instance."""
        return self.__class__(name=self.name, key=self.key)

    def process(self, game: Game):
        self.game = game

    @abstractmethod
    def decide(self):
        """Decide the next move based on the current game state."""
        pass

    def mines(self):
        """Return a list of mine locations."""
        if self.game is None:
            return []
        return self.game.mines_locs

    def enemies(self):
        """Return a list of enemy heroes."""
        if self.game is None or getattr(self.game, "hero", None) is None:
            return []
        me = self.game.hero
        return [
            h
            for h in self.game.heroes
            if h is not None
            and getattr(h, "bot_id", None) != getattr(me, "bot_id", None)
        ]

    def taverns(self):
        """Return a list of enemy heroes."""
        if self.game is None:
            return []
        return set(self.game.taverns_locs)

    def hero(self):
        """Return a list of enemy heroes."""
        if self.game is None:
            return None
        return self.game.hero

    def _package(self, path, action, decisions, hero_move):
        me = self.hero()
        taverns = self.taverns()
        mines = self.mines()
        enemies = self.enemies()
        print(f"{self.name}:  action: {action} hero_move: {hero_move}")
        me_pos = getattr(me, "pos", (0, 0))
        nearest_enemy = (
            min(
                [e for e in enemies if getattr(e, "pos", None) is not None],
                key=lambda e: abs(getattr(e, "pos", (0, 0))[0] - me_pos[0])
                + abs(getattr(e, "pos", (0, 0))[1] - me_pos[1]),
            ).pos
            if enemies and any(getattr(e, "pos", None) is not None for e in enemies)
            else me_pos
        )
        nearest_mine = (
            min(
                [
                    m
                    for m in mines
                    if m is not None and isinstance(m, (tuple, list)) and len(m) == 2
                ],
                key=lambda m: abs(m[0] - me_pos[0]) + abs(m[1] - me_pos[1]),
            )
            if mines
            and any(
                m is not None and isinstance(m, (tuple, list)) and len(m) == 2
                for m in mines
            )
            else me_pos
        )
        nearest_tavern = (
            min(
                [
                    t
                    for t in taverns
                    if t is not None and isinstance(t, (tuple, list)) and len(t) == 2
                ],
                key=lambda t: abs(t[0] - me_pos[0]) + abs(t[1] - me_pos[1]),
            )
            if taverns
            and any(
                t is not None and isinstance(t, (tuple, list)) and len(t) == 2
                for t in taverns
            )
            else me_pos
        )
        self.prev_life = getattr(me, "life", 0)

        # --- Logging decisions to CSV ---
        game = self.game
        if game and hasattr(game, "url") and game.url:
            game_id = str(game.url).rstrip("/").split("/")[-1]
            log_dir = "moves_log"
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{self.name}_{game_id}.csv")
            turn = getattr(game, "turn", None)
            gold = getattr(me, "gold", None)
            life = getattr(me, "life", None)
            num_mines = len(getattr(me, "mines", []))
            move = str(hero_move)
            timestamp = datetime.now().isoformat()
            row = [timestamp, turn, action, move, gold, life, num_mines]
            write_header = not os.path.exists(log_file)
            with open(log_file, "a", newline="") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(
                        [
                            "timestamp",
                            "turn",
                            "decision",
                            "move",
                            "gold",
                            "life",
                            "number_of_mines",
                        ]
                    )
                writer.writerow(row)
        # --- End logging ---

        return (
            path,
            action,
            decisions,
            str(hero_move),
            nearest_enemy,
            nearest_mine,
            nearest_tavern,
        )
