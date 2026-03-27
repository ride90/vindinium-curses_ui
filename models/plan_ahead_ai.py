from models.ai_base import AIBase, Actions, MapElements, Directions
from copy import deepcopy
from utils.path_finder import bfs_from_xy_to_nearest_char
from utils.grid_helpers import replace_map_values
import math


class AI(AIBase):
    MINE_GOLD_VALUE = 1
    TAVERN_HEAL_COST = 2
    TAVERN_HEAL_AMOUNT = 50
    LIFE_COST_PER_STEP = 1
    MINE_TAKE_COST = 20
    MIN_LIFE = 1

    def __init__(self, name="AIPlanAhead", key="YourKeyHere"):
        super().__init__(name, key)
        self.base_max_depth = 5  # base number of turns to plan ahead
        self.base_max_steps = 30  # base max total steps allowed in path

    def decide(self):
        start_pos = self.hero().pos
        game_copy = deepcopy(self.game)

        # Mark owned mines on the map
        owned_mines = set(game_copy.hero.mines)
        game_copy.board_map = replace_map_values(game_copy.board_map, owned_mines, "O")

        # Dynamically adjust planning depth based on game state
        remaining_turns = self.game.max_turns - self.game.turn
        self.max_depth = min(self.base_max_depth, remaining_turns)
        self.max_steps = min(self.base_max_steps, remaining_turns)

        # Start recursive exploration of action sequences
        score, sequence, path = self._explore_sequences(game_copy, start_pos, [], 0)

        if not sequence:
            # No plan found, stay put
            return self._package(
                path=[start_pos],
                action=Actions.WAIT,
                decisions={},
                hero_move=Directions.STAY,
            )

        first_action = sequence[0]
        first_step = path[1] if len(path) > 1 else start_pos
        direction = Directions.get_direction(start_pos, first_step)

        return self._package(
            path=path, action=first_action, decisions={}, hero_move=direction
        )

    def evaluate(self, game_state):
        """Evaluate the game state considering multiple factors"""
        me = game_state.hero
        remaining_turns = game_state.max_turns - game_state.turn
        enemies = [h for h in game_state.heroes if h.bot_id != me.bot_id]

        # Base score is gold
        score = me.gold

        # Add value of owned mines (future gold)
        mine_value = len(me.mines) * self.MINE_GOLD_VALUE * remaining_turns
        score += mine_value

        # Strategic positioning score
        # Bonus for being close to valuable targets when we have enough life
        if me.life > self.MINE_TAKE_COST:
            # Find nearest mine
            mines = self.mines()
            if mines:
                nearest_mine = min(
                    mines, key=lambda m: abs(m[0] - me.pos[0]) + abs(m[1] - me.pos[1])
                )
                mine_dist = abs(nearest_mine[0] - me.pos[0]) + abs(
                    nearest_mine[1] - me.pos[1]
                )
                if mine_dist < 5:  # Close to a mine
                    score += (5 - mine_dist) * 2

        # Combat readiness score
        if enemies:
            # Consider relative strength against enemies
            for enemy in enemies:
                if me.life > enemy.life + 10:  # We're stronger
                    score += 5
                elif enemy.life > me.life + 10:  # We're weaker
                    score -= 5

            # Bonus for being close to weak enemies
            weakest_enemy = min(enemies, key=lambda e: e.life)
            if weakest_enemy.life < 30:  # Enemy is weak
                enemy_dist = abs(weakest_enemy.pos[0] - me.pos[0]) + abs(
                    weakest_enemy.pos[1] - me.pos[1]
                )
                if enemy_dist < 3:  # Close to weak enemy
                    score += (3 - enemy_dist) * 3

        # Life management score
        if me.life <= 20:
            # Exponential penalty for very low life
            life_penalty = math.exp((20 - me.life) / 5) * 10
            score -= life_penalty
        elif me.life > self.MINE_TAKE_COST:
            # Bonus for having enough life to take mines
            score += 5

        # Tavern proximity score
        if me.life < 30:
            taverns = self.taverns()
            if taverns:
                nearest_tavern = min(
                    taverns, key=lambda t: abs(t[0] - me.pos[0]) + abs(t[1] - me.pos[1])
                )
                tavern_dist = abs(nearest_tavern[0] - me.pos[0]) + abs(
                    nearest_tavern[1] - me.pos[1]
                )
                if tavern_dist > me.life:
                    score -= (tavern_dist - me.life) * 2
                elif tavern_dist < 3:  # Close to tavern when low on life
                    score += (3 - tavern_dist) * 3

        # End game strategy
        if remaining_turns < 20:
            # In end game, prioritize survival and current gold over future potential
            score = score * 0.7 + me.gold * 0.3
            if me.life < 50:
                score -= 20  # Heavy penalty for low life in end game

        return score

    def decide_position_for_action(self, action, game_state, current_pos):
        board_map = game_state.board_map

        if action == Actions.TAKE_NEAREST_MINE:
            # Only look for unowned mines (not marked as 'O')
            path, dist = bfs_from_xy_to_nearest_char(
                board_map,
                current_pos,
                end_char=MapElements.MINE,
                walkable_chars={" ", MapElements.HERO},
            )
            if not path or len(path) <= 1:
                return current_pos, 0
            next_pos = path[1] if len(path) > 1 else current_pos
            return next_pos, dist

        elif action == Actions.NEAREST_TAVERN:
            path, dist = bfs_from_xy_to_nearest_char(
                board_map,
                current_pos,
                end_char=MapElements.TAVERN,
                walkable_chars={" ", MapElements.HERO},
            )
            if not path or len(path) <= 1:
                return current_pos, 0
            next_pos = path[1] if len(path) > 1 else current_pos
            return next_pos, dist

        elif action == Actions.ATTACK_NEAREST:
            path, dist = bfs_from_xy_to_nearest_char(
                board_map,
                current_pos,
                end_char=MapElements.ENEMY,
                walkable_chars={" ", MapElements.HERO},
            )
            if not path or len(path) <= 1:
                return current_pos, 0
            next_pos = path[1] if len(path) > 1 else current_pos
            return next_pos, dist

        elif action == Actions.WAIT:
            # Try to find a better position using BFS
            path, dist = bfs_from_xy_to_nearest_char(
                board_map,
                current_pos,
                end_char=" ",
                walkable_chars={" ", MapElements.HERO},
            )
            if not path or len(path) <= 1:
                return current_pos, 0
            next_pos = path[1] if len(path) > 1 else current_pos
            return next_pos, dist

        return current_pos, 0

    def apply_move(self, game_state, next_pos, n_remaining_turns, n_steps=1):
        hero = game_state.hero
        board_map = game_state.board_map

        # Reduce hero life for moving n_steps
        hero.life -= self.LIFE_COST_PER_STEP * n_steps
        hero.life = max(hero.life, self.MIN_LIFE)

        r, c = next_pos
        tile = board_map[r][c]

        if tile == MapElements.MINE:  # Mine tile
            if next_pos not in hero.mines:
                if hero.life > self.MINE_TAKE_COST:
                    # Take over mine
                    hero.mines.append(next_pos)
                    # Losing life for combat
                    hero.life -= self.MINE_TAKE_COST
                    if hero.life <= 0:
                        self._respawn_hero(hero, board_map)
                        return True

        elif tile == MapElements.ENEMY:  # Enemy hero
            enemy = self._find_enemy_at(game_state, next_pos)
            if enemy:
                # Enemy life reduced
                enemy.life -= 1
                if enemy.life <= 0:
                    # Hero wins, gets enemy's mines
                    hero.mines.extend(enemy.mines)
                    enemy.mines.clear()
                else:
                    # Hero loses, respawn
                    self._respawn_hero(hero, board_map)
                    return True

        elif tile == MapElements.TAVERN:  # Tavern tile
            if hero.gold >= self.TAVERN_HEAL_COST:
                hero.gold -= self.TAVERN_HEAL_COST
                hero.life = min(100, hero.life + self.TAVERN_HEAL_AMOUNT)

        # Update hero position
        hero.pos = next_pos

        return False  # hero did not die

    def _respawn_hero(self, hero, board_map):
        # Find spawn location '@'
        for r in range(len(board_map)):
            for c in range(len(board_map[0])):
                if board_map[r][c] == MapElements.HERO:
                    hero.pos = (r, c)
                    hero.life = 100
                    hero.mines.clear()
                    return

    def _find_enemy_at(self, game_state, pos):
        for enemy in game_state.heroes:
            if enemy.pos == pos and enemy.bot_id != game_state.hero.bot_id:
                return enemy
        return None

    def _explore_sequences(
        self,
        game_state,
        current_pos,
        action_sequence,
        current_depth,
        current_path_length=0,
    ):
        """
        Recursively explore all action sequences up to max_depth and max_steps.
        """
        # Stop exploring if max_depth or max_steps reached
        if current_depth == self.max_depth or current_path_length >= self.max_steps:
            score = self.evaluate(game_state)
            return score, action_sequence, [current_pos]

        best_score = float("-inf")
        best_sequence = None
        best_path = None

        # Prioritize actions based on game state
        hero = game_state.hero
        enemies = [h for h in game_state.heroes if h.bot_id != hero.bot_id]
        actions = []

        # Critical health check - always prioritize healing
        if hero.life < 30:
            actions.append(Actions.NEAREST_TAVERN)

        # Mine capture strategy - be more aggressive
        if hero.life > self.MINE_TAKE_COST:
            # Check if there are any unowned mines
            mines = self.mines()
            if mines and any(m not in hero.mines for m in mines):
                actions.append(Actions.TAKE_NEAREST_MINE)

        # Combat strategy - be more aggressive
        if enemies:
            weakest_enemy = min(enemies, key=lambda e: e.life)
            if hero.life > weakest_enemy.life + 5:  # Reduced threshold for attacking
                actions.append(Actions.ATTACK_NEAREST)
            elif hero.life > 40 and any(
                e.life < 40 for e in enemies
            ):  # More aggressive combat
                actions.append(Actions.ATTACK_NEAREST)

        # End game strategy
        remaining_turns = game_state.max_turns - game_state.turn
        if remaining_turns < 20:
            if hero.life < 50:
                actions.append(Actions.NEAREST_TAVERN)
            elif hero.mines and hero.life > 70:  # Defend mines in end game
                actions.append(Actions.WAIT)

        # If we have no other actions, try to move in any valid direction
        if not actions:
            actions.append(Actions.WAIT)

        # Always consider waiting as a fallback
        actions.append(Actions.WAIT)

        for action in actions:
            # Find next position for this action
            next_pos, dst = self.decide_position_for_action(
                action, game_state, current_pos
            )

            # If no move (e.g., WAIT), path length doesn't increase
            step_increment = 0 if next_pos == current_pos else dst
            new_path_length = current_path_length + step_increment

            # If path length would exceed max, skip this action
            if new_path_length > self.max_steps:
                continue

            # Simulate the move
            new_game_state = deepcopy(game_state)
            died = self.apply_move(
                new_game_state,
                next_pos,
                n_remaining_turns=self.max_depth - current_depth,
                n_steps=step_increment,
            )

            if died:
                continue  # Skip this path if hero died

            # Mark owned mines on the map after the move
            owned_mines = set(new_game_state.hero.mines)
            new_game_state.board_map = replace_map_values(
                new_game_state.board_map, owned_mines, "O"
            )

            # Recursive call with updated path length
            score, seq, path = self._explore_sequences(
                new_game_state,
                next_pos,
                action_sequence + [action],
                current_depth + 1,
                new_path_length,
            )

            if score > best_score:
                best_score = score
                best_sequence = seq
                best_path = [current_pos] + path

        return best_score, best_sequence, best_path
