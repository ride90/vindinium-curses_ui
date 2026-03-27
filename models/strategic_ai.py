from models.ai_base import AIBase, Actions, MapElements, Directions
from utils.path_finder import bfs_from_xy_to_nearest_char, bfs_from_xy_to_xy
from utils.grid_helpers import replace_map_values
from copy import deepcopy
import math


class AI(AIBase):
    MINE_GOLD_VALUE = 1
    TAVERN_HEAL_COST = 2
    TAVERN_HEAL_AMOUNT = 50
    LIFE_COST_PER_STEP = 1
    MINE_TAKE_COST = 20
    MIN_LIFE = 1

    def __init__(self, name="StrategicAI", key="YourKeyHere"):
        super().__init__(name, key)
        self.prev_positions = []  # Track previous positions to avoid loops
        self.target_mine = None  # Current target mine
        self.defensive_mode = False  # Whether we're in defensive mode
        self.last_action = None  # Track last action for continuity

    def decide(self):
        hero = self.game.hero
        game = self.game
        remaining_turns = game.max_turns - game.turn
        enemies = [h for h in game.heroes if h.bot_id != hero.bot_id]

        # Mark owned mines on the map
        owned_mines = set(hero.mines)
        game_map = replace_map_values(game.board_map, owned_mines, "O")

        # Calculate game phase
        pct = game.turn / game.max_turns
        if pct < 0.25:
            phase = "opening"
        elif pct < 0.85:
            phase = "mid"
        else:
            phase = "end"

        # Dynamic thresholds based on phase
        critical_hp = 35 if phase == "opening" else 30 if phase == "mid" else 25
        mine_threshold = 40 if phase == "opening" else 30 if phase == "mid" else 20
        combat_threshold = 50 if phase == "opening" else 40 if phase == "mid" else 30

        # Update defensive mode
        self.defensive_mode = (
            hero.life < critical_hp
            or (phase == "end" and hero.mine_count > 0)
            or any(e.life > hero.life + 20 for e in enemies)
        )

        def evaluate_position(pos):
            """Evaluate how good a position is strategically"""
            score = 0
            # Distance to nearest mine
            mine_path, mine_dist = bfs_from_xy_to_nearest_char(
                game_map, pos, MapElements.MINE
            )
            if mine_path:
                score += (10 - min(mine_dist, 10)) * 2

            # Distance to nearest tavern
            tavern_path, tavern_dist = bfs_from_xy_to_nearest_char(
                game_map, pos, MapElements.TAVERN
            )
            if tavern_path:
                score += 5 - min(tavern_dist, 5)

            # Distance to enemies
            for enemy in enemies:
                enemy_path, enemy_dist = bfs_from_xy_to_xy(game_map, pos, enemy.pos)
                if enemy_path:
                    if enemy.life < hero.life:
                        score += (5 - min(enemy_dist, 5)) * 2
                    else:
                        score -= min(enemy_dist, 5)

            return score

        def get_best_action():
            """Determine the best action based on current game state"""
            actions = []

            # Critical health check
            if hero.life < critical_hp:
                tavern_path, tavern_dist = bfs_from_xy_to_nearest_char(
                    game_map, hero.pos, MapElements.TAVERN
                )
                if tavern_path and tavern_dist < remaining_turns:
                    return tavern_path, Actions.NEAREST_TAVERN

            # Defensive strategy
            if self.defensive_mode:
                if hero.life < mine_threshold:
                    # Find safe position near owned mine
                    for mine in hero.mines:
                        path, dist = bfs_from_xy_to_xy(game_map, hero.pos, mine)
                        if path and dist < 3:
                            return path, Actions.DEFEND_MINE

                # If no safe position, try to find one
                best_pos = hero.pos
                best_score = float("-inf")
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    next_pos = (hero.pos[0] + dr, hero.pos[1] + dc)
                    if (
                        0 <= next_pos[0] < len(game_map)
                        and 0 <= next_pos[1] < len(game_map[0])
                        and game_map[next_pos[0]][next_pos[1]]
                        in {" ", MapElements.HERO}
                    ):
                        score = evaluate_position(next_pos)
                        if score > best_score:
                            best_score = score
                            best_pos = next_pos
                if best_pos != hero.pos:
                    return [hero.pos, best_pos], Actions.WAIT

            # Mine capture strategy
            if hero.life > mine_threshold and not self.defensive_mode:
                # If we have a target mine, try to reach it
                if self.target_mine:
                    path, dist = bfs_from_xy_to_xy(game_map, hero.pos, self.target_mine)
                    if path and dist < remaining_turns:
                        return path, Actions.TAKE_NEAREST_MINE

                # Find new target mine
                mine_path, mine_dist = bfs_from_xy_to_nearest_char(
                    game_map, hero.pos, MapElements.MINE
                )
                if mine_path and mine_dist < remaining_turns:
                    self.target_mine = mine_path[-1]
                    return mine_path, Actions.TAKE_NEAREST_MINE

            # Combat strategy
            if hero.life > combat_threshold and not self.defensive_mode:
                # Look for weak enemies
                for enemy in sorted(enemies, key=lambda e: e.life):
                    path, dist = bfs_from_xy_to_xy(game_map, hero.pos, enemy.pos)
                    if (
                        path
                        and dist < remaining_turns
                        and hero.life > enemy.life + dist
                    ):
                        return path, Actions.ATTACK_NEAREST

            # Default to finding best position
            best_pos = hero.pos
            best_score = float("-inf")
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                next_pos = (hero.pos[0] + dr, hero.pos[1] + dc)
                if (
                    0 <= next_pos[0] < len(game_map)
                    and 0 <= next_pos[1] < len(game_map[0])
                    and game_map[next_pos[0]][next_pos[1]] in {" ", MapElements.HERO}
                ):
                    score = evaluate_position(next_pos)
                    if score > best_score:
                        best_score = score
                        best_pos = next_pos

            if best_pos != hero.pos:
                return [hero.pos, best_pos], Actions.WAIT

            return [hero.pos], Actions.WAIT

        # Get the best action
        path, action = get_best_action()

        # Calculate direction
        if len(path) > 1:
            direction = Directions.get_direction(path[0], path[1])
        else:
            direction = Directions.STAY

        # Update state
        self.last_action = action
        if len(path) > 1:
            self.prev_positions.append(path[1])
            if len(self.prev_positions) > 5:
                self.prev_positions.pop(0)

        return self._package(
            path=path, action=action, decisions={}, hero_move=direction
        )
