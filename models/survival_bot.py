from enum import Enum

from models.ai_base import AIBase, Actions, MapElements, Directions
from utils.grid_helpers import replace_map_values
from utils.path_finder import bfs_from_xy_to_xy, bfs_from_xy_to_nearest_char


class AI(AIBase):

    def decide(self):
        hero = self.game.hero
        game = self.game
        remaining_turns = game.max_turns - game.turn
        enemies = [h for h in game.heroes if h.bot_id != hero.bot_id]
        enemies_by_mines = sorted(enemies, key=lambda h: h.mine_count, reverse=True)

        owned_mines = set(hero.mines)
        game_map = self.game.board_map
        game_map = replace_map_values(game_map, owned_mines, "O")

        def should_do_nearest_mine():
            path, distance = bfs_from_xy_to_nearest_char(
                game_map, hero.pos, MapElements.MINE
            )
            if distance < remaining_turns:
                return path, Actions.TAKE_NEAREST_MINE
            else:
                return None

        def should_attack_richest():
            richest = enemies_by_mines[0]
            path, distance = bfs_from_xy_to_xy(game_map, hero.pos, richest.pos)
            if distance < remaining_turns and hero.life >= richest.life:
                return path, Actions.ATTACK_RICHEST
            return None

        def should_attack_nearest():
            path, distance = bfs_from_xy_to_nearest_char(
                game_map, hero.pos, MapElements.ENEMY
            )
            if len(path) > 0:
                enemy_position = path[-1]
                enemy = [
                    e
                    for e in enemies
                    if e.pos[0] == enemy_position[0] and e.pos[1] == enemy_position[1]
                ]
                if (
                    distance < remaining_turns
                    and len(enemy) > 0
                    and enemy[0].life <= hero.life
                ):
                    return path, Actions.ATTACK_NEAREST
            return None

        def should_go_to_tavern():
            path, distance = bfs_from_xy_to_nearest_char(
                game_map, hero.pos, MapElements.TAVERN
            )
            if distance < remaining_turns:
                return path, Actions.NEAREST_TAVERN
            return None

        def wait():
            return [hero.pos, hero.pos], Actions.WAIT

        policy_priority = [
            should_do_nearest_mine,
            should_attack_richest,
            should_attack_nearest,
            should_go_to_tavern,
            wait,
        ]
        path_and_action = None
        i = 0

        while path_and_action is None:
            path_and_action = policy_priority[i]()
            i += 1
        move = Directions.get_direction(hero.pos, path_and_action[0][1])
        # If nothing to do, stay still or chase random enemy mine
        print(
            f"---- {self.name} has decided to: {path_and_action[1]} and move to the {move}"
        )

        return self._package(
            path=path_and_action[0],
            action=path_and_action[1],
            decisions=[path_and_action[1]],
            hero_move=move,
        )
