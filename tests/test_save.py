from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from crucible_echoes.engine import GameEngine
from crucible_echoes.save import load_game, save_game


class SaveTests(unittest.TestCase):
    def test_json_round_trip_preserves_rng_sequence(self) -> None:
        engine = GameEngine(); engine.new_game(314159)
        engine.spin(); engine.skip()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            save_game(engine.s, path)
            resumed = GameEngine().bind(load_game(path))
            engine.spin(); resumed.spin()
            self.assertEqual(engine.s.last_board, resumed.s.last_board)
            self.assertEqual(engine.s.pending[0].offers, resumed.s.pending[0].offers)
            self.assertEqual(engine.s.rng_state, resumed.s.rng_state)


if __name__ == "__main__":
    unittest.main()

