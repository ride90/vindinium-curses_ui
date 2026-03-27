from models.ai_base import AIBase, Actions, MapElements, Directions
from utils.path_finder import bfs_from_xy_to_nearest_char, bfs_from_xy_to_xy
from utils.grid_helpers import replace_map_values
from copy import deepcopy
import json
import os
import math


class AI(AIBase):
    MINE_GOLD_VALUE = 1
    TAVERN_HEAL_COST = 2
    TAVERN_HEAL_AMOUNT = 50
    LIFE_COST_PER_STEP = 1
    MINE_TAKE_COST = 20
    MIN_LIFE = 1

    def __init__(self, name="PatternAI", key="YourKeyHere"):
        super().__init__(name, key)
        self.patterns_file = "data/learned_patterns.json"
        self.state_file = "data/game_state.json"
        self.patterns = self._load_patterns()
        self.game_state = self._load_state()
        self.current_pattern = None
        self.pattern_success_count = 0
        self.pattern_failure_count = 0

    def _load_patterns(self):
        """Load learned patterns from file"""
        if os.path.exists(self.patterns_file):
            with open(self.patterns_file, "r") as f:
                return json.load(f)
        return {
            "opening": [],  # Patterns for game start
            "mid": [],  # Patterns for mid game
            "end": [],  # Patterns for end game
            "success_rates": {},  # Track success rates of patterns
        }

    def _save_patterns(self):
        """Save learned patterns to file"""
        os.makedirs(os.path.dirname(self.patterns_file), exist_ok=True)
        with open(self.patterns_file, "w") as f:
            json.dump(self.patterns, f)

    def _load_state(self):
        """Load game state from file"""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                return json.load(f)
        return {
            "games_played": 0,
            "total_gold": 0,
            "total_mines": 0,
            "successful_patterns": {},
            "failed_patterns": {},
        }

    def _save_state(self):
        """Save game state to file"""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.game_state, f)

    def decide(self):
        hero = self.game.hero
        game = self.game
        remaining_turns = game.max_turns - game.turn
        enemies = [h for h in game.heroes if h.bot_id != hero.bot_id]

        # Mark owned mines on the map
        owned_mines = set(hero.mines)
        game_map = replace_map_values(game.board_map, owned_mines, "O")

        # Determine game phase
        pct = game.turn / game.max_turns
        if pct < 0.25:
            phase = "opening"
        elif pct < 0.85:
            phase = "mid"
        else:
            phase = "end"

        # Get current situation signature
        situation = self._get_situation_signature(hero, enemies, game_map)

        # Find matching pattern or create new one
        pattern = self._find_matching_pattern(situation, phase)
        if pattern:
            self.current_pattern = pattern
            action = self._execute_pattern(
                pattern, game_map, hero, enemies, remaining_turns
            )
        else:
            # No matching pattern, use default strategy
            action = self._default_strategy(game_map, hero, enemies, remaining_turns)
            # Record this as a new pattern
            self._record_new_pattern(situation, action, phase)

        # Calculate direction
        if len(action["path"]) > 1:
            direction = Directions.get_direction(action["path"][0], action["path"][1])
        else:
            direction = Directions.STAY

        return self._package(
            path=action["path"],
            action=action["action"],
            decisions={},
            hero_move=direction,
        )

    def _get_situation_signature(self, hero, enemies, game_map):
        """Create a signature for the current game situation"""
        return {
            "hero_life": hero.life,
            "hero_mines": len(hero.mines),
            "hero_gold": hero.gold,
            "enemy_count": len(enemies),
            "enemy_life_avg": (
                sum(e.life for e in enemies) / len(enemies) if enemies else 0
            ),
            "enemy_mines_avg": (
                sum(len(e.mines) for e in enemies) / len(enemies) if enemies else 0
            ),
            "nearest_tavern": self._get_nearest_distance(
                game_map, hero.pos, MapElements.TAVERN
            ),
            "nearest_mine": self._get_nearest_distance(
                game_map, hero.pos, MapElements.MINE
            ),
            "nearest_enemy": self._get_nearest_enemy_distance(hero, enemies),
        }

    def _get_nearest_distance(self, game_map, pos, target):
        """Get distance to nearest target using BFS"""
        path, dist = bfs_from_xy_to_nearest_char(
            game_map, pos, target, walkable_chars={" ", MapElements.HERO}
        )
        return dist if path else float("inf")

    def _get_nearest_enemy_distance(self, hero, enemies):
        """Get distance to nearest enemy using BFS"""
        if not enemies:
            return float("inf")
        min_dist = float("inf")
        for enemy in enemies:
            path, dist = bfs_from_xy_to_xy(
                self.game.board_map,
                hero.pos,
                enemy.pos,
                walkable_chars={" ", MapElements.HERO},
            )
            if path and dist < min_dist:
                min_dist = dist
        return min_dist

    def _find_matching_pattern(self, situation, phase):
        """Find a pattern that matches the current situation"""
        best_pattern = None
        best_score = float("-inf")

        for pattern in self.patterns[phase]:
            score = self._calculate_pattern_match_score(situation, pattern["situation"])
            if score > best_score:
                best_score = score
                best_pattern = pattern

        return best_pattern if best_score > 0.7 else None

    def _calculate_pattern_match_score(self, situation1, situation2):
        """Calculate how well two situations match"""
        score = 0
        total_weights = 0

        # Define weights for different aspects
        weights = {
            "hero_life": 0.2,
            "hero_mines": 0.15,
            "hero_gold": 0.1,
            "enemy_count": 0.1,
            "enemy_life_avg": 0.15,
            "enemy_mines_avg": 0.1,
            "nearest_tavern": 0.1,
            "nearest_mine": 0.05,
            "nearest_enemy": 0.05,
        }

        for key, weight in weights.items():
            if key in situation1 and key in situation2:
                # Normalize differences
                if key in ["hero_life", "enemy_life_avg"]:
                    diff = abs(situation1[key] - situation2[key]) / 100
                elif key in ["nearest_tavern", "nearest_mine", "nearest_enemy"]:
                    diff = abs(situation1[key] - situation2[key]) / 10
                else:
                    diff = abs(situation1[key] - situation2[key]) / max(
                        1, max(situation1[key], situation2[key])
                    )

                score += (1 - diff) * weight
                total_weights += weight

        return score / total_weights if total_weights > 0 else 0

    def _execute_pattern(self, pattern, game_map, hero, enemies, remaining_turns):
        """Execute a learned pattern using BFS pathfinding"""
        action = pattern["action"]

        if action == Actions.NEAREST_TAVERN:
            path, dist = bfs_from_xy_to_nearest_char(
                game_map,
                hero.pos,
                MapElements.TAVERN,
                walkable_chars={" ", MapElements.HERO},
            )
            if path and dist < remaining_turns:
                return {"path": path, "action": action}

        elif action == Actions.TAKE_NEAREST_MINE:
            path, dist = bfs_from_xy_to_nearest_char(
                game_map,
                hero.pos,
                MapElements.MINE,
                walkable_chars={" ", MapElements.HERO},
            )
            if path and dist < remaining_turns:
                return {"path": path, "action": action}

        elif action == Actions.ATTACK_NEAREST:
            for enemy in enemies:
                if hero.life > enemy.life + 10:
                    path, dist = bfs_from_xy_to_xy(
                        game_map,
                        hero.pos,
                        enemy.pos,
                        walkable_chars={" ", MapElements.HERO},
                    )
                    if path and dist < remaining_turns:
                        return {"path": path, "action": action}

        # If pattern execution fails, fall back to default strategy
        return self._default_strategy(game_map, hero, enemies, remaining_turns)

    def _default_strategy(self, game_map, hero, enemies, remaining_turns):
        """Default strategy when no pattern matches, using BFS pathfinding"""
        # Critical health check
        if hero.life < 30:
            tavern_path, tavern_dist = bfs_from_xy_to_nearest_char(
                game_map,
                hero.pos,
                MapElements.TAVERN,
                walkable_chars={" ", MapElements.HERO},
            )
            if tavern_path and tavern_dist < remaining_turns:
                return {"path": tavern_path, "action": Actions.NEAREST_TAVERN}

        # Mine capture
        if hero.life > self.MINE_TAKE_COST:
            mine_path, mine_dist = bfs_from_xy_to_nearest_char(
                game_map,
                hero.pos,
                MapElements.MINE,
                walkable_chars={" ", MapElements.HERO},
            )
            if mine_path and mine_dist < remaining_turns:
                return {"path": mine_path, "action": Actions.TAKE_NEAREST_MINE}

        # Combat
        for enemy in enemies:
            if hero.life > enemy.life + 10:
                path, dist = bfs_from_xy_to_xy(
                    game_map,
                    hero.pos,
                    enemy.pos,
                    walkable_chars={" ", MapElements.HERO},
                )
                if path and dist < remaining_turns:
                    return {"path": path, "action": Actions.ATTACK_NEAREST}

        # Default to waiting
        return {"path": [hero.pos], "action": Actions.WAIT}

    def _record_new_pattern(self, situation, action, phase):
        """Record a new pattern"""
        pattern = {
            "situation": situation,
            "action": action["action"],
            "success_count": 0,
            "failure_count": 0,
        }
        self.patterns[phase].append(pattern)
        self._save_patterns()

    def update_pattern_success(self, success):
        """Update pattern success/failure counts"""
        if self.current_pattern:
            if success:
                self.current_pattern["success_count"] += 1
                self.pattern_success_count += 1
            else:
                self.current_pattern["failure_count"] += 1
                self.pattern_failure_count += 1

            # Update success rate
            total = (
                self.current_pattern["success_count"]
                + self.current_pattern["failure_count"]
            )
            if total > 0:
                self.patterns["success_rates"][
                    str(self.current_pattern["situation"])
                ] = (self.current_pattern["success_count"] / total)

            self._save_patterns()

    def end_game(self, final_gold, final_mines):
        """Called at the end of each game to update statistics"""
        self.game_state["games_played"] += 1
        self.game_state["total_gold"] += final_gold
        self.game_state["total_mines"] += final_mines

        # Update pattern success rates
        if self.current_pattern:
            success_rate = self.pattern_success_count / (
                self.pattern_success_count + self.pattern_failure_count
            )
            if success_rate > 0.5:
                self.game_state["successful_patterns"][
                    str(self.current_pattern["situation"])
                ] = success_rate
            else:
                self.game_state["failed_patterns"][
                    str(self.current_pattern["situation"])
                ] = success_rate

        self._save_state()

        # Reset counters
        self.current_pattern = None
        self.pattern_success_count = 0
        self.pattern_failure_count = 0
