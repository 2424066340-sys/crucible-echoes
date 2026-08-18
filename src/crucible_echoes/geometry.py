from __future__ import annotations

BASE_COORDS = [(row, col) for row in range(4) for col in range(5)]
EXPANSION_COORD = (-1, 2)


def board_coords(expanded: bool) -> list[tuple[int, int]]:
    return ([EXPANSION_COORD] if expanded else []) + BASE_COORDS


def adjacent_indices(coords: list[tuple[int, int]], index: int) -> list[int]:
    row, col = coords[index]
    return [
        other
        for other, (other_row, other_col) in enumerate(coords)
        if other != index and abs(other_row - row) <= 1 and abs(other_col - col) <= 1
    ]


def is_edge(coord: tuple[int, int]) -> bool:
    row, col = coord
    return coord == EXPANSION_COORD or row in (0, 3) or col in (0, 4)


def is_corner(coord: tuple[int, int]) -> bool:
    return coord in {(0, 0), (0, 4), (3, 0), (3, 4)}

