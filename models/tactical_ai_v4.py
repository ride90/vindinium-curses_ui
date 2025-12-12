from models.ai_base import AIBase, Actions, MapElements, Directions
from utils.grid_helpers import replace_map_values
from utils.path_finder import bfs_from_xy_to_xy, bfs_from_xy_to_nearest_char


class AI(AIBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.explore_path = None
        self.explore_objective = None  # e.g., "attack_enemy" or "take_unowned_mine"

    def clone(self):
        new_ai = super().clone()
        new_ai.explore_path = self.explore_path
        new_ai.explore_objective = self.explore_objective
        return new_ai

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
        remaining_turns = getattr(game, "max_turns", 0) - getattr(game, "turn", 0)
        enemies = [
            h
            for h in getattr(game, "heroes", [])
            if getattr(h, "bot_id", None) != getattr(hero, "bot_id", None)
        ]
        enemies_by_mines = sorted(
            enemies, key=lambda h: getattr(h, "mine_count", 0), reverse=True
        )

        owned_mines = set(getattr(hero, "mines", []))
        game_map = getattr(self.game, "board_map", [])
        game_map = replace_map_values(game_map, owned_mines, "O")

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
                        decisions=[Actions.NEAREST_TAVERN],
                        hero_move=move,
                    )
        # --- End recharge logic ---

        is_leading = all(hero.mine_count >= e.mine_count for e in enemies)

        just_respawned = (
            self.prev_life is not None and self.prev_life <= 0 and hero.life == 100
        )

        pct = game.turn / game.max_turns
        if just_respawned or pct < 0.25:
            phase = "opening"
        elif pct < 0.85:
            phase = "mid"
        else:
            phase = "end"

        critical_hp = 35 if phase == "opening" else 30 if phase == "mid" else 25

        def calculate_mine_value(distance):
            # Calculate if taking a mine is worth it based on remaining turns
            cost = 20  # HP cost to take mine
            turns_to_reach = distance
            turns_earning = remaining_turns - turns_to_reach
            if turns_earning <= 0:
                return False
            # Only take mine if we can earn back the HP cost in gold
            return hero.life - turns_to_reach - 20 > 1

        def defend_mines_if():
            for mine_pos in hero.mines:
                for enemy in enemies:
                    path, distance = bfs_from_xy_to_xy(game_map, enemy.pos, mine_pos)
                    if distance < 3 and hero.life > enemy.life + distance:
                        intercept_pathA, intercept_distanceA = bfs_from_xy_to_xy(
                            game_map, hero.pos, path[0]
                        )
                        intercept_pathB, intercept_distanceB = bfs_from_xy_to_xy(
                            game_map, hero.pos, mine_pos
                        )
                        intercept_path, intercept_distance = (
                            (intercept_pathA, intercept_distanceA)
                            if intercept_distanceA < intercept_distanceB
                            else (intercept_pathB, intercept_distanceB)
                        )
                        if len(intercept_path) > 0:
                            self.explore_path = None
                            self.explore_objective = None
                            return intercept_path, Actions.DEFEND_MINE
            return None

        def end_game_if():
            path, distance = bfs_from_xy_to_nearest_char(
                game_map, hero.pos, MapElements.TAVERN
            )
            if phase == "end" and is_leading and distance <= remaining_turns:
                self.explore_path = None
                self.explore_objective = None
                return path, Actions.ENDGAME_TAVERN
            else:
                return None

        def do_nearest_if():
            path, distance = bfs_from_xy_to_nearest_char(
                game_map, hero.pos, MapElements.MINE
            )
            if distance < remaining_turns and calculate_mine_value(distance):
                self.explore_path = None
                self.explore_objective = None
                return path, Actions.TAKE_NEAREST_MINE
            else:
                return None

        def attack_richest_if():
            richest = enemies_by_mines[0]
            path, distance = bfs_from_xy_to_xy(game_map, hero.pos, richest.pos)
            if (
                distance < remaining_turns
                and hero.life - distance - 1 >= richest.life
                and hero.life > critical_hp + distance * 5
            ):
                if richest.mine_count >= 3:
                    self.explore_path = None
                    self.explore_objective = None
                    return path, Actions.ATTACK_RICHEST
                elif hero.life > richest.life * 1.5:
                    self.explore_path = None
                    self.explore_objective = None
                    return path, Actions.ATTACK_RICHEST
            return None

        def opportunistic_kill_if():
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
                    distance < 4
                    and len(enemy) > 0
                    and enemy[0].life <= hero.life - distance - 1
                ):
                    self.explore_path = None
                    self.explore_objective = None
                    return path, Actions.ATTACK_NEAREST
            return None

        def attack_nearest_if():
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
                    and enemy[0].life <= hero.life - distance - 1
                ):
                    self.explore_path = None
                    self.explore_objective = None
                    return path, Actions.ATTACK_NEAREST
            return None

        def attack_weakest_if():
            weakest = min(enemies, key=lambda e: e.life)
            path, distance = bfs_from_xy_to_xy(game_map, hero.pos, weakest.pos)
            if weakest.life < hero.life - distance - 1 and distance < remaining_turns:
                self.explore_path = None
                self.explore_objective = None
                return path, Actions.ATTACK_WEAKEST
            return None

        def go_to_tavern_if():
            path, distance = bfs_from_xy_to_nearest_char(
                game_map, hero.pos, MapElements.TAVERN
            )
            if (
                distance < remaining_turns
                and hero.life < critical_hp
                and hero.gold >= 2
                and (hero.life + 50 - distance) * hero.mine_count > 2
            ):
                self.explore_path = None
                self.explore_objective = None
                return path, Actions.NEAREST_TAVERN
            return None

        def suicide():
            if hero.mine_count == 0 and hero.gold == 0:
                path_1, distance_1 = bfs_from_xy_to_nearest_char(
                    game_map, hero.pos, MapElements.ENEMY
                )
                path_2, distance_2 = bfs_from_xy_to_nearest_char(
                    game_map, hero.pos, MapElements.MINE
                )
                path, distance = (
                    (path_1, distance_1)
                    if distance_1 < distance_2
                    else (path_2, distance_2)
                )
                if distance < remaining_turns * 2:
                    self.explore_path = None
                    self.explore_objective = None
                    return path, Actions.SUICIDE
            return None

        import random

        def explore_if_factory(objective):
            def inner():
                # Default objective if not set
                if not self.explore_objective:
                    self.explore_objective = objective

                # If we already have a path, follow it
                if self.explore_path and len(self.explore_path) > 1:
                    if hero.pos == self.explore_path[0]:
                        self.explore_path.pop(0)
                    if len(self.explore_path) > 1:
                        return (self.explore_path[:2], Actions.EXPLORE)
                    else:
                        self.explore_path = None

                # Determine target based on objective
                if self.explore_objective == "attack_enemy":
                    target_enemy = max(
                        enemies, key=lambda e: e.mine_count, default=None
                    )
                    if not target_enemy:
                        return None
                    target_pos = target_enemy.pos
                elif self.explore_objective == "take_unowned_mine":
                    unowned_mines = [
                        m for m in getattr(game, "mines", []) if m not in owned_mines
                    ]
                    if not unowned_mines:
                        return None
                    # Pick the farthest unowned mine to encourage exploration
                    unowned_mines = sorted(
                        unowned_mines,
                        key=lambda pos: abs(pos[0] - hero.pos[0])
                        + abs(pos[1] - hero.pos[1]),
                        reverse=True,
                    )
                    target_pos = unowned_mines[0]
                else:
                    return None

                # Plan path to target
                path_to_target, dist_to_target = bfs_from_xy_to_xy(
                    game_map, hero.pos, target_pos
                )

                # If life is too low to reach, plan a tavern stop
                if hero.life < dist_to_target * 5 + 20:
                    taverns = list(getattr(game, "taverns_locs", []))
                    if not taverns:
                        return None
                    # Find the tavern with the shortest actual path to the target
                    best_tavern = None
                    best_distance = float("inf")
                    for t in taverns:
                        _, dist = bfs_from_xy_to_xy(game_map, t, target_pos)
                        if dist is not None and dist < best_distance:
                            best_tavern = t
                            best_distance = dist
                    tavern_near_target = best_tavern
                    if tavern_near_target is None:
                        return None
                    path_to_tavern, dist_to_tavern = bfs_from_xy_to_xy(
                        game_map, hero.pos, tavern_near_target
                    )
                    path_tavern_to_target, _ = bfs_from_xy_to_xy(
                        game_map, tavern_near_target, target_pos
                    )
                    full_path = path_to_tavern + path_tavern_to_target[1:]
                    self.explore_path = full_path
                    return (full_path[:2], Actions.EXPLORE)
                else:
                    self.explore_path = path_to_target
                    return (path_to_target[:2], Actions.EXPLORE)

            return inner

        def wait():
            return [hero.pos, hero.pos], Actions.WAIT

        policy_priority = [
            end_game_if,
            defend_mines_if,
            go_to_tavern_if,
            opportunistic_kill_if,
            do_nearest_if,
            attack_richest_if,
            attack_weakest_if,
            attack_nearest_if,
            suicide,
            explore_if_factory("take_unowned_mine"),
            explore_if_factory("attack_enemy"),
            wait,
        ]

        path_and_action = None
        i = 0

        while path_and_action is None:
            path_and_action = policy_priority[i]()
            i += 1

        # Safety check: ensure path has at least 2 elements for direction calculation
        if path_and_action is None or len(path_and_action[0]) < 2:
            # Fallback to wait action - print comprehensive debug info
            print("=== FALLBACK TRIGGERED - DEBUG INFO ===")
            print(f"Hero position: {getattr(hero, 'pos', 'None')}")
            print(f"Hero life: {getattr(hero, 'life', 'None')}")
            print(f"Hero gold: {getattr(hero, 'gold', 'None')}")
            print(f"Hero mines: {getattr(hero, 'mines', 'None')}")
            print(f"Hero mine_count: {getattr(hero, 'mine_count', 'None')}")
            print(f"Remaining turns: {remaining_turns}")
            print(f"Phase: {phase}")
            print(f"Critical HP: {critical_hp}")
            print(f"Enemies count: {len(enemies)}")

            # Print nearest targets info
            try:
                nearest_mine_path, nearest_mine_dist = bfs_from_xy_to_nearest_char(
                    game_map, getattr(hero, "pos", (0, 0)), MapElements.MINE
                )
                print(
                    f"Nearest mine: path={nearest_mine_path}, distance={nearest_mine_dist}"
                )
            except Exception as e:
                print(f"Error getting nearest mine: {e}")

            try:
                nearest_enemy_path, nearest_enemy_dist = bfs_from_xy_to_nearest_char(
                    game_map, getattr(hero, "pos", (0, 0)), MapElements.ENEMY
                )
                print(
                    f"Nearest enemy: path={nearest_enemy_path}, distance={nearest_enemy_dist}"
                )
            except Exception as e:
                print(f"Error getting nearest enemy: {e}")

            try:
                nearest_tavern_path, nearest_tavern_dist = bfs_from_xy_to_nearest_char(
                    game_map, getattr(hero, "pos", (0, 0)), MapElements.TAVERN
                )
                print(
                    f"Nearest tavern: path={nearest_tavern_path}, distance={nearest_tavern_dist}"
                )
            except Exception as e:
                print(f"Error getting nearest tavern: {e}")

            # Print game map
            print("Game map:")
            try:
                for i, row in enumerate(game_map):
                    print(f"Row {i}: {row}")
            except Exception as e:
                print(f"Error printing game map: {e}")

            # Print enemy details
            print("Enemies:")
            for i, enemy in enumerate(enemies):
                print(
                    f"  Enemy {i}: pos={getattr(enemy, 'pos', 'None')}, life={getattr(enemy, 'life', 'None')}, mines={getattr(enemy, 'mines', 'None')}, mine_count={getattr(enemy, 'mine_count', 'None')}"
                )

            # Print policy results
            print("Policy results:")
            for i, policy in enumerate(policy_priority):
                try:
                    result = policy()
                    print(f"  Policy {i}: {policy.__name__} = {result}")
                except Exception as e:
                    print(f"  Policy {i}: {policy.__name__} = ERROR: {e}")

            print("=== END DEBUG INFO ===")

            # Fallback to wait action
            path_and_action = (
                [getattr(hero, "pos", (0, 0)), getattr(hero, "pos", (0, 0))],
                Actions.WAIT,
            )

        move = Directions.get_direction(hero.pos, path_and_action[0][1])
        # If nothing to do, stay still or chase random enemy mine
        return self._package(
            path=path_and_action[0],
            action=path_and_action[1],
            decisions=[path_and_action[1]],
            hero_move=move,
        )
