from utils.grid_helpers import replace_map_values, plot_path_on_map
from utils.path_finder import bfs_from_char_to_nearest_char

if __name__ == "__main__":
    game_map = [
        "###X######X###",
        "$############$",
        " ####    #### ",
        "H#T#      #T##",
        "   $      $   ",
        "##   ####   ##",
        "$  # $##$ #  $",
        "$  # $##$ #  $",
        "##   ####   ##",
        "   $      $   ",
        "H#T#      #T#@",
        " ####    #### ",
        "$############$",
        "###X######X###",
    ]
    game_map = replace_map_values(game_map, [(0, 1)], "u")

    # Define what's walkable for general path movement
    # Based on the prompt: "#": wall, "T": tavern, "$": Mine, "H": Hero
    # "None of the elements, apart from the heroes can be moved accross."
    # This implies H, T, $ are obstacles. Only ' ' (space) is walkable.
    # The end_char ('X' or 'H' in our tests) will be the *final* cell we can step onto.
    walkable_terrain = {" "}

    # Scenario 1: Hero steps INTO 'X'
    print("--- Scenario 1: Hero steps INTO 'X' ---")
    shortest_path_X, path_length_X = bfs_from_char_to_nearest_char(
        game_map, end_char="X", start_char="@", walkable=walkable_terrain
    )

    if shortest_path_X:
        mapped_path_X = plot_path_on_map(
            game_map, shortest_path_X, start_char="@", final_path_marker="*"
        )
        print(f"Path Length (steps): {path_length_X}")
        print("\nPath Coordinates (last coordinate is the target 'X'):")
        print(shortest_path_X)
        print("\nMap with Shortest Path ('.' for path, '*' for target 'X'):")
        for row in mapped_path_X:
            print(row)
    else:
        print("No path found to any 'X'.")

    print("\n" + "=" * 50 + "\n")

    # Scenario 2: Hero steps INTO 'H'
    print("--- Scenario 2: Hero attempts to step INTO 'H' ---")
    shortest_path_to_H, path_length_to_H = bfs_from_char_to_nearest_char(
        game_map, end_char="H", start_char="@", walkable=walkable_terrain
    )

    if shortest_path_to_H:
        mapped_path_to_H = plot_path_on_map(
            game_map, shortest_path_to_H, start_char="@", final_path_marker="*"
        )
        print(f"Path Length (steps): {path_length_to_H}")
        print("\nPath Coordinates (last coordinate is the target 'H'):")
        print(shortest_path_to_H)
        print("\nMap with Shortest Path ('.' for path, '*' for target 'H'):")
        for row in mapped_path_to_H:
            print(row)
    else:
        print(
            "No path found to step into 'H'. (This is expected if 'H' is surrounded by non-walkable cells apart from the path itself)"
        )
