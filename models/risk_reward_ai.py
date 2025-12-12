from models.ai_base import AIBase, Actions, MapElements, Directions
from utils.path_finder import bfs_from_xy_to_nearest_char, bfs_from_xy_to_xy
from utils.grid_helpers import replace_map_values
from copy import deepcopy
import random
import math


class AI(AIBase):
    MINE_GOLD_VALUE = 1
    TAVERN_HEAL_COST = 2
    TAVERN_HEAL_AMOUNT = 50
    LIFE_COST_PER_STEP = 1
    MINE_TAKE_COST = 20
    MIN_LIFE = 1

    # Risk thresholds
    BASE_RISK_THRESHOLD = 0.7  # Base risk threshold (0-1)
    MIN_RISK_THRESHOLD = 0.3  # Minimum risk threshold
    MAX_RISK_THRESHOLD = 0.9  # Maximum risk threshold

    # Monte Carlo parameters
    SIMULATION_DEPTH = 3  # How many turns to simulate
    SIMULATION_COUNT = 10  # Number of simulations per action

    def __init__(self, name="RiskRewardAI", key="YourKeyHere"):
        super().__init__(name, key)
        self.risk_threshold = self.BASE_RISK_THRESHOLD
        self.prev_actions = []  # Track previous actions for pattern recognition

    def decide(self):
        if self.game is None or getattr(self.game, "hero", None) is None:
            return self._package(
                path=[(0, 0)],
                action=Actions.WAIT,
                decisions={},
                hero_move=Directions.STAY,
            )
        hero = self.game.hero
        game = self.game
        # --- Recharge if next to tavern, have gold, and life < 65 ---
        taverns = set(getattr(self.game, "taverns_locs", []))
        y, x = getattr(hero, "pos", (0, 0))
        adjacent = [(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)]
        if (
            any(t in taverns for t in adjacent)
            and getattr(hero, "gold", 0) >= 2
            and getattr(hero, "life", 100) < 65
        ):
            # Move to the adjacent tavern
            for t in adjacent:
                if t in taverns:
                    path = [getattr(hero, "pos", (0, 0)), t]
                    move = Directions.get_direction(getattr(hero, "pos", (0, 0)), t)
                    return self._package(
                        path=path,
                        action=Actions.NEAREST_TAVERN,
                        decisions={"reason": "adjacent tavern recharge"},
                        hero_move=move,
                    )
        # --- End recharge logic ---
        remaining_turns = getattr(game, "max_turns", 0) - getattr(game, "turn", 0)
        enemies = [
            h
            for h in getattr(game, "heroes", [])
            if getattr(h, "bot_id", None) != getattr(hero, "bot_id", None)
        ]

        # Mark owned mines on the map
        owned_mines = set(getattr(hero, "mines", []))
        game_map = getattr(game, "board_map", [])
        game_map = replace_map_values(game_map, owned_mines, "O")

        # Update risk threshold based on game state
        self._update_risk_threshold(hero, enemies, remaining_turns)

        # Get all possible actions with their risk-reward profiles
        actions = self._get_possible_actions(game_map, hero, enemies, remaining_turns)

        if not actions:
            return self._package(
                path=[getattr(hero, "pos", (0, 0))],
                action=Actions.WAIT,
                decisions={},
                hero_move=Directions.STAY,
            )

        # Select best action based on risk-reward profile
        best_action = self._select_best_action(actions)

        # Calculate direction
        if len(best_action["path"]) > 1:
            direction = Directions.get_direction(
                best_action["path"][0], best_action["path"][1]
            )
        else:
            direction = Directions.STAY

        # Update action history
        self.prev_actions.append(best_action["action"])
        if len(self.prev_actions) > 5:
            self.prev_actions.pop(0)

        return self._package(
            path=best_action["path"],
            action=best_action["action"],
            decisions={},
            hero_move=direction,
        )

    def _update_risk_threshold(self, hero, enemies, remaining_turns):
        """Dynamically update risk threshold based on game state"""
        # Base threshold
        threshold = self.BASE_RISK_THRESHOLD

        # Adjust based on health
        if hero.life < 30:
            threshold -= 0.2
        elif hero.life > 70:
            threshold += 0.1

        # Adjust based on mine count
        if hero.mine_count > 0:
            threshold -= 0.1 * min(hero.mine_count, 3)

        # Adjust based on remaining turns
        if remaining_turns < 20:
            threshold += 0.2

        # Adjust based on enemy strength
        for enemy in enemies:
            if enemy.life > hero.life + 20:
                threshold -= 0.1
            elif enemy.life < hero.life - 20:
                threshold += 0.1

        # Keep within bounds
        self.risk_threshold = max(
            self.MIN_RISK_THRESHOLD, min(self.MAX_RISK_THRESHOLD, threshold)
        )

    def _get_possible_actions(self, game_map, hero, enemies, remaining_turns):
        """Get all possible actions with their risk-reward profiles"""
        actions = []

        # Check for tavern visits
        if hero.life < 40:
            tavern_path, tavern_dist = bfs_from_xy_to_nearest_char(
                game_map,
                hero.pos,
                MapElements.TAVERN,
                walkable_chars={" ", MapElements.HERO},
            )
            if tavern_path and tavern_dist < remaining_turns:
                risk = self._calculate_tavern_risk(hero, tavern_dist)
                reward = self._calculate_tavern_reward(hero)
                actions.append(
                    {
                        "path": tavern_path,
                        "action": Actions.NEAREST_TAVERN,
                        "risk": risk,
                        "reward": reward,
                        "turns": tavern_dist,
                    }
                )

        # Check for mine captures
        if hero.life > self.MINE_TAKE_COST:
            mine_path, mine_dist = bfs_from_xy_to_nearest_char(
                game_map,
                hero.pos,
                MapElements.MINE,
                walkable_chars={" ", MapElements.HERO},
            )
            if mine_path and mine_dist < remaining_turns:
                risk = self._calculate_mine_risk(hero, mine_dist, enemies)
                reward = self._calculate_mine_reward(remaining_turns)
                actions.append(
                    {
                        "path": mine_path,
                        "action": Actions.TAKE_NEAREST_MINE,
                        "risk": risk,
                        "reward": reward,
                        "turns": mine_dist,
                    }
                )

        # Check for combat opportunities
        for enemy in enemies:
            if hero.life > enemy.life + 10:
                path, dist = bfs_from_xy_to_xy(game_map, hero.pos, enemy.pos)
                if path and dist < remaining_turns:
                    risk = self._calculate_combat_risk(hero, enemy, dist)
                    reward = self._calculate_combat_reward(enemy)
                    actions.append(
                        {
                            "path": path,
                            "action": Actions.ATTACK_NEAREST,
                            "risk": risk,
                            "reward": reward,
                            "turns": dist,
                        }
                    )

        # Add wait action as fallback
        actions.append(
            {
                "path": [hero.pos],
                "action": Actions.WAIT,
                "risk": 0.1,
                "reward": 0.1,
                "turns": 0,
            }
        )

        return actions

    def _calculate_tavern_risk(self, hero, distance):
        """Calculate risk of visiting tavern"""
        # Risk increases with distance and low health
        base_risk = distance * 0.1
        health_risk = (40 - hero.life) * 0.02
        return min(0.9, base_risk + health_risk)

    def _calculate_tavern_reward(self, hero):
        """Calculate reward of visiting tavern"""
        # Reward is higher when health is lower
        return (100 - hero.life) * 0.02

    def _calculate_mine_risk(self, hero, distance, enemies):
        """Calculate risk of capturing mine"""
        # Base risk from distance
        risk = distance * 0.1

        # Additional risk from enemies
        for enemy in enemies:
            enemy_path, enemy_dist = bfs_from_xy_to_xy(
                self.game.board_map, enemy.pos, hero.pos
            )
            if enemy_dist < distance + 2:
                risk += 0.2

        return min(0.9, risk)

    def _calculate_mine_reward(self, remaining_turns):
        """Calculate reward of capturing mine"""
        # Reward is based on remaining turns
        return remaining_turns * self.MINE_GOLD_VALUE

    def _calculate_combat_risk(self, hero, enemy, distance):
        """Calculate risk of combat"""
        # Base risk from distance
        risk = distance * 0.1

        # Additional risk based on health difference
        health_diff = enemy.life - hero.life
        if health_diff > 0:
            risk += health_diff * 0.02

        return min(0.9, risk)

    def _calculate_combat_reward(self, enemy):
        """Calculate reward of combat"""
        # Reward is based on enemy's mine count
        return enemy.mine_count * 2

    def _select_best_action(self, actions):
        """Select best action based on risk-reward profile"""
        best_action = None
        best_score = float("-inf")

        for action in actions:
            # Calculate risk-adjusted reward
            risk_adjusted_reward = action["reward"] * (1 - action["risk"])

            # Apply Monte Carlo simulation
            simulated_reward = self._monte_carlo_simulation(action)

            # Combine immediate and simulated rewards
            total_score = risk_adjusted_reward + simulated_reward

            if total_score > best_score:
                best_score = total_score
                best_action = action

        return best_action

    def _monte_carlo_simulation(self, action):
        """Perform Monte Carlo simulation for an action"""
        total_reward = 0

        for _ in range(self.SIMULATION_COUNT):
            game_copy = deepcopy(self.game)
            current_reward = 0

            # Simulate the action
            if action["action"] == Actions.TAKE_NEAREST_MINE:
                current_reward += self._simulate_mine_capture(game_copy, action["path"])
            elif action["action"] == Actions.ATTACK_NEAREST:
                current_reward += self._simulate_combat(game_copy, action["path"])
            elif action["action"] == Actions.NEAREST_TAVERN:
                current_reward += self._simulate_tavern_visit(game_copy, action["path"])

            total_reward += current_reward

        return total_reward / self.SIMULATION_COUNT

    def _simulate_mine_capture(self, game_copy, path):
        """Simulate mine capture outcome"""
        if len(path) <= 1:
            return 0

        hero = game_copy.hero
        next_pos = path[1]

        # Check if we can take the mine
        if hero.life > self.MINE_TAKE_COST:
            return self.MINE_GOLD_VALUE * (game_copy.max_turns - game_copy.turn)
        return 0

    def _simulate_combat(self, game_copy, path):
        """Simulate combat outcome"""
        if len(path) <= 1:
            return 0

        hero = game_copy.hero
        next_pos = path[1]

        # Find enemy at position
        for enemy in game_copy.heroes:
            if enemy.bot_id != hero.bot_id and enemy.pos == next_pos:
                if hero.life > enemy.life:
                    return enemy.mine_count * 2
        return 0

    def _simulate_tavern_visit(self, game_copy, path):
        """Simulate tavern visit outcome"""
        if len(path) <= 1:
            return 0

        hero = game_copy.hero
        if hero.gold >= self.TAVERN_HEAL_COST:
            return (100 - hero.life) * 0.5
        return 0
