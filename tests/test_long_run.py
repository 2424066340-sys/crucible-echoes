from __future__ import annotations

import unittest

from crucible_echoes.engine import GameEngine


class LongRunTests(unittest.TestCase):
    def test_seeded_run_can_reach_victory_through_all_reward_queues(self) -> None:
        engine = GameEngine(); engine.new_game(987654, difficulty=10)
        engine.s.gold = 1_000_000  # isolate state-machine endurance from balance
        spins = 0
        while engine.s.status == "playing" and spins < 400:
            while engine.s.pending:
                engine.choose(1)
            if engine.s.status != "playing":
                break
            engine.spin()
            spins += 1
        self.assertEqual("won", engine.s.status)
        self.assertEqual(13, engine.s.order_index)
        self.assertLess(spins, 400)


if __name__ == "__main__":
    unittest.main()
