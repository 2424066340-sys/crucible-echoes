from __future__ import annotations

import unittest

from crucible_echoes.engine import GameEngine, GameError


class OrdersTokensEssencesTests(unittest.TestCase):
    def test_order_curve_and_cumulative_difficulty_bonuses(self) -> None:
        engine = GameEngine(); engine.new_game(1, difficulty=10)
        expected = {7: 375, 8: 450, 9: 600, 10: 650, 11: 700}
        for order_number, amount in expected.items():
            actual, _ = engine.current_order_for(order_number - 1, 10, {})
            self.assertEqual(amount, actual)
        self.assertEqual((1350, 15), engine.current_order_for(12, 10, {}))
        self.assertEqual((1000, 10), engine.current_order_for(12, 1, {}))

    def test_initial_slag_and_interval_rules(self) -> None:
        for difficulty, count in ((1,0),(5,1),(6,2),(8,3),(10,3)):
            engine = GameEngine(); engine.new_game(1, difficulty)
            self.assertEqual(count, sum(x.def_id == "slag" for x in engine.s.ingredients))
        self.assertEqual(25, GameEngine.slag_interval(7))
        self.assertEqual(20, GameEngine.slag_interval(8))
        self.assertEqual(15, GameEngine.slag_interval(10))

    def test_even_order_awards_tokens_with_cumulative_per_token_rules(self) -> None:
        for difficulty, expected_remove, expected_roll, expected_essence in ((1,2,2,2),(4,1,1,2),(10,1,1,1)):
            engine = GameEngine(); engine.new_game(1, difficulty)
            engine.s.order_index = 3
            engine.s.spins_left = 1
            engine.s.gold = 9999
            engine.spin()
            self.assertEqual(expected_roll, engine.s.tokens["roll"])
            self.assertEqual(expected_remove, engine.s.tokens["remove"])
            self.assertEqual(0, engine.s.tokens["essence"])
            essence_choices = [x for x in engine.s.pending if x.kind == "essence"]
            self.assertEqual(expected_essence, len(essence_choices))

    def test_d10_final_order_requires_extra_thirteen_order(self) -> None:
        engine = GameEngine(); engine.new_game(1, difficulty=10)
        engine.s.order_index = 11
        engine.s.spins_left = 1
        engine.s.gold = 1350
        engine.spin()
        self.assertEqual("playing", engine.s.status)
        self.assertEqual(12, engine.s.order_index)
        self.assertEqual(15, engine.s.spins_left)
        self.assertEqual((1350, 15), engine.current_order())

    def test_reroll_and_removal_tokens_are_consumed(self) -> None:
        engine = GameEngine(); engine.new_game(4)
        engine.spin()
        old = list(engine.s.pending[0].offers)
        engine.s.tokens["roll"] = 1
        engine.reroll()
        self.assertEqual(0, engine.s.tokens["roll"])
        self.assertNotEqual(old, engine.s.pending[0].offers)
        engine.skip()
        engine.s.tokens["remove"] = 1
        size = len(engine.s.ingredients)
        engine.remove(1)
        self.assertEqual(size - 1, len(engine.s.ingredients))
        self.assertEqual(0, engine.s.tokens["remove"])

    def test_slag_cannot_be_manually_removed(self) -> None:
        engine = GameEngine(); engine.new_game(5, difficulty=5)
        slag_index = next(i for i,x in enumerate(engine.s.ingredients,1) if x.def_id == "slag")
        engine.s.tokens["remove"] = 1
        with self.assertRaises(GameError):
            engine.remove(slag_index)

    def test_essence_condition_triggers_and_is_consumed(self) -> None:
        engine = GameEngine(); engine.new_game(9)
        engine.s.ingredients.clear()
        for def_id in ("test_tube", "measuring_cylinder", "flask"):
            engine.add_ingredient(def_id, emit=False)
        engine.add_essence("test_tube_rack_essence")
        engine.spin()
        self.assertNotIn("test_tube_rack_essence", engine.s.essences)
        self.assertIn("test_tube_rack_essence", engine.s.consumed_essences)
        self.assertTrue(all(x.permanent_bonus == 2 for x in engine.s.ingredients))


if __name__ == "__main__":
    unittest.main()
