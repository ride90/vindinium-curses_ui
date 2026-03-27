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

    def __init__(self, name="HybridAI", key="YourKeyHere"):
        super().__init__(name, key)
        self.strategy_weights = {
            "survival": 1.0,  # Focus on staying alive
            "mining": 1.0,  # Focus on capturing mines
            "combat": 1.0,  # Focus on combat
            "economic": 1.0,  # Focus on gold generation
            "defensive": 1.0,  # Focus on defending mines
        }
        self.prev_actions = []  # Track previous actions for strategy adjustment

    def decide(self):
        hero = self.game.hero
        game = self.game
        remaining_turns = game.max_turns - game.turn
        enemies = [h for h in game.heroes if h.bot_id != hero.bot_id]

        # Mark owned mines on the map
        owned_mines = set(hero.mines)
        game_map = replace_map_values(game.board_map, owned_mines, "O")

        # Update strategy weights based on game state
        self._update_strategy_weights(hero, enemies, remaining_turns)

        # Get votes from each strategy
        strategy_votes = self._get_strategy_votes(
            game_map, hero, enemies, remaining_turns
        )

        # Combine votes and select best action
        best_action = self._combine_votes(strategy_votes)

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

    def _update_strategy_weights(self, hero, enemies, remaining_turns):
        """Update strategy weights based on game state"""
        # Calculate game phase
        pct = remaining_turns / self.game.max_turns

        # Survival strategy
        if hero.life < 30:
            self.strategy_weights["survival"] = 2.0
        else:
            self.strategy_weights["survival"] = 1.0

        # Mining strategy
        if hero.life > self.MINE_TAKE_COST and hero.mine_count < 2:
            self.strategy_weights["mining"] = 1.5
        else:
            self.strategy_weights["mining"] = 1.0

        # Combat strategy
        if any(e.life < hero.life - 10 for e in enemies):
            self.strategy_weights["combat"] = 1.5
        else:
            self.strategy_weights["combat"] = 1.0

        # Economic strategy
        if pct < 0.3:  # End game
            self.strategy_weights["economic"] = 1.5
        else:
            self.strategy_weights["economic"] = 1.0

        # Defensive strategy
        if hero.mine_count > 0 and any(e.life > hero.life for e in enemies):
            self.strategy_weights["defensive"] = 1.5
        else:
            self.strategy_weights["defensive"] = 1.0

    def _get_strategy_votes(self, game_map, hero, enemies, remaining_turns):
        """Get votes from each strategy"""
        votes = []

        # Survival strategy vote
        if hero.life < 40:
            tavern_path, tavern_dist = bfs_from_xy_to_nearest_char(
                game_map,
                hero.pos,
                MapElements.TAVERN,
                walkable_chars={" ", MapElements.HERO},
            )
            if tavern_path and tavern_dist < remaining_turns:
                votes.append(
                    {
                        "path": tavern_path,
                        "action": Actions.NEAREST_TAVERN,
                        "strategy": "survival",
                        "weight": self.strategy_weights["survival"],
                    }
                )

        # Mining strategy vote
        if hero.life > self.MINE_TAKE_COST:
            mine_path, mine_dist = bfs_from_xy_to_nearest_char(
                game_map,
                hero.pos,
                MapElements.MINE,
                walkable_chars={" ", MapElements.HERO},
            )
            if mine_path and mine_dist < remaining_turns:
                votes.append(
                    {
                        "path": mine_path,
                        "action": Actions.TAKE_NEAREST_MINE,
                        "strategy": "mining",
                        "weight": self.strategy_weights["mining"],
                    }
                )

        # Combat strategy vote
        for enemy in enemies:
            if hero.life > enemy.life + 10:
                path, dist = bfs_from_xy_to_xy(game_map, hero.pos, enemy.pos)
                if path and dist < remaining_turns:
                    votes.append(
                        {
                            "path": path,
                            "action": Actions.ATTACK_NEAREST,
                            "strategy": "combat",
                            "weight": self.strategy_weights["combat"],
                        }
                    )
                    break

        # Economic strategy vote
        if hero.mine_count > 0:
            # Find position that maximizes gold generation
            best_pos = hero.pos
            best_score = float("-inf")
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                next_pos = (hero.pos[0] + dr, hero.pos[1] + dc)
                if (
                    0 <= next_pos[0] < len(game_map)
                    and 0 <= next_pos[1] < len(game_map[0])
                    and game_map[next_pos[0]][next_pos[1]] in {" ", MapElements.HERO}
                ):
                    score = self._calculate_economic_score(next_pos, hero, enemies)
                    if score > best_score:
                        best_score = score
                        best_pos = next_pos
            if best_pos != hero.pos:
                votes.append(
                    {
                        "path": [hero.pos, best_pos],
                        "action": Actions.WAIT,
                        "strategy": "economic",
                        "weight": self.strategy_weights["economic"],
                    }
                )

        # Defensive strategy vote
        if hero.mine_count > 0:
            for mine in hero.mines:
                path, dist = bfs_from_xy_to_xy(game_map, hero.pos, mine)
                if path and dist < 3:
                    votes.append(
                        {
                            "path": path,
                            "action": Actions.DEFEND_MINE,
                            "strategy": "defensive",
                            "weight": self.strategy_weights["defensive"],
                        }
                    )
                    break

        # Add wait action as fallback
        votes.append(
            {
                "path": [hero.pos],
                "action": Actions.WAIT,
                "strategy": "survival",
                "weight": 0.5,
            }
        )

        return votes

    def _calculate_economic_score(self, pos, hero, enemies):
        """Calculate economic score for a position"""
        score = 0

        # Distance to owned mines
        for mine in hero.mines:
            dist = abs(pos[0] - mine[0]) + abs(pos[1] - mine[1])
            score += 5 - min(dist, 5)

        # Distance to enemies
        for enemy in enemies:
            dist = abs(pos[0] - enemy.pos[0]) + abs(pos[1] - enemy.pos[1])
            if dist < 3:
                score -= (3 - dist) * 2

        return score

    def _combine_votes(self, votes):
        """Combine votes from different strategies"""
        if not votes:
            return {"path": [self.game.hero.pos], "action": Actions.WAIT}

        # Calculate weighted scores for each action
        action_scores = {}
        for vote in votes:
            key = (vote["action"], tuple(vote["path"]))
            if key not in action_scores:
                action_scores[key] = 0
            action_scores[key] += vote["weight"]

        # Find action with highest score
        best_key = max(action_scores.items(), key=lambda x: x[1])[0]
        return {"path": list(best_key[1]), "action": best_key[0]}
