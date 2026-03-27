#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vindinium heuristic AI — **v3.2: marginal‑value mines & distance penalty**
=======================================================================

Two strategy tweaks requested:

1. **No hard mine cap.**  We now capture a mine whenever its *marginal value*
   (remaining turns minus rough breakeven) is positive, instead of stopping at
   7/5/2.
2. **Distance penalty.**  The farther the mine, the less attractive.  The rule
   used is

   ```python
   worth = remaining_turns – path_len – 10
   ```
   …so a mine one step away "pays for itself" if ≥ 10 turns remain; a mine 6
   steps away needs ≥ 16 turns, etc.

No other behaviour changed.  Still pure standard‑library.
"""

from collections import deque
from typing import List, Tuple, Any

from models.ai_base import AIBase, MapElements, Directions
from utils.path_finder import bfs_from_xy_to_xy, bfs_from_xy_to_nearest_char
from utils.grid_helpers import replace_map_values


class AI(AIBase):
    """Phase‑aware greedy Vindinium bot adaptive to any max‑turn setting using shared path finding."""

    def __init__(self, name="HeuristicAI", key="YourKeyHere"):
        super().__init__(name, key)
        self.nearby_heal_threshold = (
            60  # Configurable health threshold for nearby healing
        )
        self.nearby_tavern_distance = (
            2  # Configurable distance to consider a tavern "nearby"
        )
        self.prev_positions = []  # Track previous positions
        self.max_position_history = 5  # How many positions to track

    def decide(self):
        if self.game is None or getattr(self.game, "hero", None) is None:
            return self._package(
                [(0, 0)], "Hold", [("phase", "unknown")], Directions.STAY
            )
        g = self.game
        me = g.hero
        turn: int = g.turn
        TOTAL: int = getattr(g, "max_turns", 150)
        remaining = TOTAL - turn

        # --------------------------------------------------------------
        # Phase detection + mini‑opening after respawn
        # --------------------------------------------------------------
        just_respawned = (
            self.prev_life is not None and self.prev_life <= 0 and me.life == 100
        )
        pct = turn / TOTAL
        if just_respawned or pct < 0.25:
            phase = "opening"
        elif pct < 0.85:
            phase = "mid"
        else:
            phase = "end"

        critical_hp = 35 if phase == "opening" else 30 if phase == "mid" else 25

        # --------------------------------------------------------------
        # Board state
        # --------------------------------------------------------------
        taverns = set(getattr(g, "taverns_locs", []))
        all_mines = set(getattr(g, "mines_locs", []))
        owned_mines = set(getattr(me, "mines", []))
        mines = all_mines - owned_mines  # only neutral/enemy mines
        enemies = [
            h
            for h in getattr(g, "heroes", [])
            if getattr(h, "bot_id", None) != getattr(me, "bot_id", None)
        ]

        # Use the board_map and mark owned mines as 'O'
        game_map = replace_map_values(
            getattr(g, "board_map", []), owned_mines, MapElements.OWNED_MINE
        )

        dbg = [("phase", phase)]

        # 1. Heal if low or near tavern with low health -----------------
        if taverns and getattr(me, "gold", 0) >= 2:
            me_pos = getattr(me, "pos", (0, 0))
            me_life = getattr(me, "life", 100)
            # Check for nearby taverns
            nearby_taverns = [
                t
                for t in taverns
                if abs(me_pos[0] - t[0]) + abs(me_pos[1] - t[1])
                <= self.nearby_tavern_distance
            ]
            if (me_life <= critical_hp) or (
                nearby_taverns and me_life <= self.nearby_heal_threshold
            ):
                if nearby_taverns:
                    tavern = nearby_taverns[0]
                    path = [me_pos, tavern]
                else:
                    path, dist = bfs_from_xy_to_nearest_char(
                        game_map, me_pos, MapElements.TAVERN
                    )
                    tavern = path[-1] if path else None
                if path:
                    dbg.append(("heal", str(tavern)))
                    move = (
                        Directions.get_direction(me_pos, path[1])
                        if len(path) > 1
                        else Directions.STAY
                    )
                    return self._package(path, "Heal", dbg, move)

        # 2. Opportunistic kill ---------------------------------------
        for e in sorted(enemies, key=lambda h: getattr(h, "life", 100)):
            if getattr(e, "life", 100) > 40:
                continue
            e_pos = getattr(e, "pos", (0, 0))
            path, dist = bfs_from_xy_to_xy(game_map, me_pos, e_pos)
            if path and dist <= 5:
                dbg.append(("kill", str(getattr(e, "bot_id", ""))))
                move = (
                    Directions.get_direction(me_pos, path[1])
                    if len(path) > 1
                    else Directions.STAY
                )
                return self._package(path, "Kill", dbg, move)

        # 3. Capture mine (marginal‑value rule) ------------------------
        if mines:
            # Find the nearest mine (not owned)
            path, dist = bfs_from_xy_to_nearest_char(game_map, me_pos, MapElements.MINE)
            mine = path[-1] if path else None
            if path:
                path_len = len(path) - 1
                worth = (
                    remaining - path_len - 10
                )  # 10‑turn breakeven + distance penalty
                if worth > 0:
                    dbg.append(("mine", str(mine)))
                    move = (
                        Directions.get_direction(me_pos, path[1])
                        if len(path) > 1
                        else Directions.STAY
                    )
                    return self._package(path, "Mine", dbg, move)

        # 4. Default: hold --------------------------------------------
        return self._package([me_pos], "Hold", dbg, Directions.STAY)

    # ---------------------------- helper -----------------------------


if __name__ == "__main__":
    print("AI module loaded – hand control to the engine.")
