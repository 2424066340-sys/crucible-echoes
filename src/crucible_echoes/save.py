from __future__ import annotations

import json
from pathlib import Path

from .model import GameState


def save_game(state: GameState, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def load_game(path: str | Path) -> GameState:
    source = Path(path)
    return GameState.from_dict(json.loads(source.read_text(encoding="utf-8")))

