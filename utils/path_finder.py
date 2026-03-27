import collections

NOT_FOUND = [], float("inf")
DEFAULT_WALKABLE_CHARS = {" ", "X"}


def bfs_from_xy_to_xy(grid, start_pos, target_pos, walkable_chars={" "}):
    """
    Core BFS function to find the shortest path in a grid to a specific coordinate.
    Hero steps into the target coordinate.

    Args:
        grid (list of str): The map represented as a list of strings.
        start_pos (tuple): The (row, col) coordinates of the starting position.
        target_pos (tuple): The (row, col) coordinates of the destination.
        walkable_chars (set): A set of characters that represent terrain the hero can walk over.

    Returns:
        tuple: A tuple containing the path (list of coordinates) and its length.
               Returns (None, 0) if no path is found.
    """
    rows, cols = len(grid), len(grid[0])
    ALL_WALKABLE_CHARS = DEFAULT_WALKABLE_CHARS.union(walkable_chars)
    # Validate start and target positions
    if not rows or not cols:
        return NOT_FOUND
    if not (0 <= start_pos[0] < rows and 0 <= start_pos[1] < cols):
        print(f"Error: Start position {start_pos} is out of map bounds.")
        return NOT_FOUND
    if not (0 <= target_pos[0] < rows and 0 <= target_pos[1] < cols):
        print(f"Error: Target position {target_pos} is out of map bounds.")
        return NOT_FOUND

    # Ensure the target position itself is not a hard obstacle (like '#')
    # If the target is an obstacle, it's unreachable
    if grid[target_pos[0]][target_pos[1]] not in ALL_WALKABLE_CHARS:
        # If target character is not in walkable_chars and it's not a space, it's likely an obstacle
        # unless it's a specific end character we define (like 'X' or 'H' if we could walk *on* them).
        # For a specific coordinate, we assume we can step *on* it if it's not a wall.
        # Let's consider '#' always an obstacle for target position.
        if grid[target_pos[0]][target_pos[1]] == "#":
            print(
                f"Error: Target position {target_pos} contains an impassable obstacle ('#')."
            )
            return NOT_FOUND

    queue = collections.deque([(start_pos, [start_pos])])
    visited = {start_pos}

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # Up, Down, Left, Right

    while queue:
        (r, c), path = queue.popleft()

        # If the current cell is the target coordinate
        if (r, c) == target_pos:
            return path, len(path) - 1

        # Explore neighbors
        for dr, dc in directions:
            nr, nc = r + dr, c + dc

            # Check boundaries
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue

            neighbor_char = grid[nr][nc]

            # Check if the neighbor is walkable. The target itself is handled by the "if (r,c) == target_pos" above.
            # We must *not* include characters that are impassable walls (like '#').
            # We assume anything *not* in walkable_chars, and not the target, is an obstacle.
            is_valid_move = neighbor_char in ALL_WALKABLE_CHARS

            # The target itself can be moved onto, so we explicitly allow moving onto the target coordinate.
            if (nr, nc) == target_pos:
                is_valid_move = True

            # Check if not visited and is a valid move
            if is_valid_move and (nr, nc) not in visited:
                visited.add((nr, nc))
                new_path = list(path)
                new_path.append((nr, nc))
                queue.append(((nr, nc), new_path))

    return NOT_FOUND  # No path found


def bfs_from_xy_to_nearest_char(grid, start_pos, end_char, walkable_chars={" "}):
    """
    Core BFS function to find the shortest path in a grid.
    Hero steps into the target location.

    Args:
        grid (list of str): The map represented as a list of strings.
        start_pos (tuple): The (row, col) coordinates of the starting position.
        end_char (str): The character representing the destination.
        walkable_chars (set): A set of characters that represent terrain the hero can walk over.
                             The `end_char` is implicitly considered walkable for the final step.

    Returns:
        tuple: A tuple containing the path (list of coordinates) and its length.
               Returns (None, 0) if no path is found.
    """
    rows, cols = len(grid), len(grid[0])

    # Handle empty grid or invalid start_pos
    if (
        not rows
        or not cols
        or not (0 <= start_pos[0] < rows and 0 <= start_pos[1] < cols)
    ):
        return NOT_FOUND

    queue = collections.deque([(start_pos, [start_pos])])
    visited = {start_pos}

    # Define possible moves (Up, Down, Left, Right)
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    ALL_WALKABLE_CHARS = DEFAULT_WALKABLE_CHARS.union(walkable_chars)

    while queue:
        (r, c), path = queue.popleft()

        # If the current cell is the destination character, we've found the path
        if grid[r][c] == end_char:
            return path, len(path) - 1  # Path includes start, so subtract 1 for steps

        # Explore neighbors
        for dr, dc in directions:
            nr, nc = r + dr, c + dc

            # Check boundaries
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue

            neighbor_char = grid[nr][nc]

            # Check if the neighbor is generally walkable OR if it's the specific end_char
            is_valid_move = (neighbor_char in ALL_WALKABLE_CHARS) or (
                neighbor_char == end_char
            )

            # Check if not visited
            if is_valid_move and (nr, nc) not in visited:
                visited.add((nr, nc))
                new_path = list(path)  # Create a new list for each path branch
                new_path.append((nr, nc))
                queue.append(((nr, nc), new_path))

    return NOT_FOUND  # No path found


def bfs_from_char_to_nearest_char(grid, end_char, start_char="@", walkable={" "}):
    """
    Finds the shortest path from a starting character to an ending character in a grid,
    where the hero steps into the target location.

    Args:
        grid (list of str): The map represented as a list of strings.
        start_char (str): The character representing the starting position.
        end_char (str): The character representing the destination.
        walkable (set): A set of characters that represent terrain the hero can walk over.

    Returns:
        tuple: A tuple containing the path (list of coordinates) and its length.
               Returns (None, 0) if no path is found.
    """
    rows, cols = len(grid), len(grid[0])
    start_pos = None

    # Find the starting position based on start_char
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == start_char:
                start_pos = (r, c)
                break
        if start_pos:
            break

    if not start_pos:
        print(f"Error: Start character '{start_char}' not found.")
        return NOT_FOUND

    # Call the new core BFS function
    return bfs_from_xy_to_nearest_char(grid, start_pos, end_char, walkable)
