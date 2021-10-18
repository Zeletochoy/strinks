from typing import Iterable

from editdistance import eval as edit_distance


def best_match(query: str, choices: Iterable[str]) -> int:
    best_idx = 0
    best_ed = len(query)
    for i, choice in enumerate(choices):
        distance = edit_distance(query, choice)
        if distance < best_ed:
            best_idx = i
            best_ed = distance
    return best_idx
