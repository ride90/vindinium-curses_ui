def plot_path_on_map(grid, path, start_char="@", final_path_marker="*"):
    """
    Modifies the grid to show the shortest path, where the hero steps *into* the target location.

    Args:
        grid (list of str): The original map.
        path (list of tuple): The list of coordinates representing the path.
                              The last coordinate in the path is the target location.
        start_char (str): The character for the starting position.
        final_path_marker (str): The character to mark the final destination cell with.

    Returns:
        list of str: The modified map with the path plotted.
    """
    if not path:
        return grid

    mutable_grid = [list(row) for row in grid]

    # Mark the path with '?' (excluding start and the final destination)
    for r, c in path[1:-1]:
        mutable_grid[r][c] = "?"

    # Mark the final destination cell with the specified marker
    if len(path) > 0:  # Ensure path is not empty
        dest_r, dest_c = path[-1]
        # Only mark if it's not the start position itself (e.g., if start_char == end_char)
        if mutable_grid[dest_r][dest_c] != start_char:
            mutable_grid[dest_r][dest_c] = final_path_marker

    # Convert back to a list of strings
    return ["".join(row) for row in mutable_grid]


def replace_map_values(map_grid, replacements, new_char):
    """
    Replaces characters at specified coordinates in a map grid.

    Args:
        map_grid (list of str): The original map represented as a list of strings.
        replacements (list of tuple): A list where each tuple is
                                      (row, col, new_char) indicating the
                                      coordinate and the new character to place there.

    Returns:
        list of str: A new list of strings representing the modified map.
                     Returns the original map if replacements is empty or None.
    """
    if not map_grid or not replacements:
        return list(map_grid)  # Return a copy to ensure immutability is maintained

    rows = len(map_grid)
    cols = len(map_grid[0]) if rows > 0 else 0

    # Convert the list of strings to a mutable list of lists of characters
    mutable_grid = [list(row) for row in map_grid]

    for r, c in replacements:
        # Validate coordinates
        if 0 <= r < rows and 0 <= c < cols:
            mutable_grid[r][c] = new_char
        else:
            print(
                f"Warning: Coordinates ({r}, {c}) are out of bounds for the map. Skipping replacement '{new_char}'."
            )

    # Convert the mutable grid back to a list of strings
    return ["".join(row) for row in mutable_grid]
