from __future__ import annotations

import unittest

from crucible_echoes.catalog import Catalog
from crucible_echoes.engine import GameEngine


class CatalogAndRarityTests(unittest.TestCase):
    def test_catalog_is_large_and_cross_references_are_valid(self) -> None:
        catalog = Catalog.load()
        self.assertEqual([], catalog.validate())
        self.assertGreaterEqual(len(catalog.ingredients), 120)
        self.assertGreaterEqual(len(catalog.items), 80)
        self.assertGreaterEqual(len(catalog.essences), 80)

    def test_base_rarity_tables_sum_to_one_hundred(self) -> None:
        catalog = Catalog.load()
        for table_name in ("ingredient_rarity", "item_rarity"):
            for row in catalog.progression[table_name].values():
                self.assertAlmostEqual(100.0, sum(row))

    def test_high_to_low_rarity_multiplier_compresses_lower_tiers(self) -> None:
        engine = GameEngine()
        engine.new_game(seed=7)
        engine.s.order_index = 5
        before = engine.rarity_table("ingredient")
        engine.add_ingredient("copper")
        after = engine.rarity_table("ingredient")
        self.assertAlmostEqual(100.0, sum(after))
        self.assertGreater(after[3], before[3])
        self.assertGreater(after[2], before[2])
        self.assertLess(after[0], before[0])

    def test_seed_reproduces_board_and_offer(self) -> None:
        left = GameEngine(); right = GameEngine()
        left.new_game(seed=20260818); right.new_game(seed=20260818)
        left.spin(); right.spin()
        self.assertEqual(left.s.last_board, right.s.last_board)
        self.assertEqual(left.s.pending[0].offers, right.s.pending[0].offers)
        self.assertEqual(left.s.rng_state, right.s.rng_state)


if __name__ == "__main__":
    unittest.main()

