from __future__ import annotations

from collections import defaultdict
import unittest

from crucible_echoes.engine import GameEngine
from crucible_echoes.model import GameState


class BalanceExtensionTests(unittest.TestCase):
    def fresh(self) -> GameEngine:
        engine = GameEngine()
        engine.new_game(20260819)
        engine.s.ingredients.clear()
        engine.s.items.clear()
        engine.s.essences.clear()
        engine.s.consumed_essences.clear()
        engine.s.gold = 0
        engine._round_events = defaultdict(int)
        engine._round_event_values = defaultdict(int)
        return engine

    def test_ore_sorting_table_only_guarantees_first_mineral(self) -> None:
        engine = self.fresh()
        engine.s.items.append("ore_sorting_table")
        first = engine._spawn_random(tag="stone", rarity=1)
        second = engine._spawn_random(tag="stone", rarity=1)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertGreaterEqual(int(engine.catalog.ingredients[first.def_id]["rarity"]), 2)
        self.assertEqual(1, int(engine.catalog.ingredients[second.def_id]["rarity"]))

    def test_ore_sorting_table_and_vein_minimum_do_not_stack(self) -> None:
        table = self.fresh()
        table.s.items.append("ore_sorting_table")
        calls: list[float] = []
        table.r.random = lambda: calls.append(0.0) or 0.0
        created = table._spawn_random(
            tag="stone",
            rarity=1,
            minimum_rarity_chance={"chance": 1.0, "minimum": 2},
        )
        self.assertIsNotNone(created)
        self.assertGreaterEqual(int(table.catalog.ingredients[created.def_id]["rarity"]), 2)
        # The redundant vein-style chance is not rolled after the table already
        # guarantees 2; only the definition selection consumes random().
        self.assertEqual(1, len(calls))

        ordinary = self.fresh()
        ordinary.r.random = lambda: 0.99
        low = ordinary._spawn_random(
            tag="stone",
            rarity=1,
            minimum_rarity_chance={"chance": 0.0, "minimum": 2},
        )
        high = ordinary._spawn_random(
            tag="stone",
            rarity=1,
            minimum_rarity_chance={"chance": 1.0, "minimum": 2},
        )
        self.assertEqual(1, int(ordinary.catalog.ingredients[low.def_id]["rarity"]))
        self.assertGreaterEqual(int(ordinary.catalog.ingredients[high.def_id]["rarity"]), 2)

    def test_vein_periodic_spawn_uses_normal_and_high_quality_paths(self) -> None:
        for random_value, minimum in ((0.99, 1), (0.0, 2)):
            engine = self.fresh()
            vein = engine.add_ingredient("vein", emit=False)
            vein.counter = 5
            engine._board = [vein]
            engine._coords = [(0, 0)]
            engine._values = [0]
            engine.r.random = lambda value=random_value: value
            engine._run_active_effects()
            generated = [x for x in engine.s.ingredients if x.uid != vein.uid]
            self.assertEqual(1, len(generated))
            self.assertGreaterEqual(int(engine.catalog.ingredients[generated[0].def_id]["rarity"]), minimum)
            self.assertEqual(1, vein.permanent_bonus)
            self.assertEqual(0, vein.counter)

    def _run_summon_attempt(self, engine: GameEngine, success: bool) -> None:
        engine._chance = lambda _chance, result=success: result
        source = next(x for x in engine.s.ingredients if x.def_id == "summon_magic")
        engine._board = [source]
        engine._coords = [(0, 0)]
        engine._values = [0]
        before = len(engine.s.ingredients)
        engine._run_active_effects()
        if success:
            self.assertEqual(before + 1, len(engine.s.ingredients))
        else:
            self.assertEqual(before, len(engine.s.ingredients))

    def test_summon_magic_guarantees_fourth_success_then_resets(self) -> None:
        engine = self.fresh()
        engine.add_ingredient("summon_magic", emit=False)
        for _ in range(3):
            self._run_summon_attempt(engine, True)
        self.assertEqual(3, engine.s.stats["spawn_counters"]["summon_magic"])
        self._run_summon_attempt(engine, True)
        fourth = engine.s.ingredients[-1]
        self.assertGreaterEqual(int(engine.catalog.ingredients[fourth.def_id]["rarity"]), 2)
        self.assertEqual(0, engine.s.stats["spawn_counters"]["summon_magic"])
        self._run_summon_attempt(engine, True)
        self.assertEqual(1, int(engine.catalog.ingredients[engine.s.ingredients[-1].def_id]["rarity"]))
        self.assertEqual(1, engine.s.stats["spawn_counters"]["summon_magic"])

    def test_summon_failure_does_not_advance_counter(self) -> None:
        engine = self.fresh()
        engine.add_ingredient("summon_magic", emit=False)
        self._run_summon_attempt(engine, False)
        self.assertEqual(0, engine.s.stats["spawn_counters"].get("summon_magic", 0))
        self._run_summon_attempt(engine, True)
        self.assertEqual(1, engine.s.stats["spawn_counters"]["summon_magic"])

    def test_impossible_container_essence_rewards_75_and_removes_five_common(self) -> None:
        engine = self.fresh()
        for _ in range(35):
            engine.add_ingredient("water", emit=False)
        engine.add_essence("impossible_container_essence")
        engine.check_essences()
        self.assertEqual(75, engine.s.gold)
        self.assertEqual(30, len(engine.s.ingredients))
        self.assertIn("impossible_container_essence", engine.s.consumed_essences)
        self.assertGreaterEqual(engine.s.stats["event_counts"]["removed"], 5)
        self.assertTrue(all(engine.catalog.ingredients[x.def_id]["rarity"] == 1 for x in engine.s.ingredients))

    def test_crowded_lab_threshold_and_once_per_round(self) -> None:
        for count, expected in ((29, 0), (30, 3)):
            engine = self.fresh()
            engine.s.items.append("crowded_lab")
            for _ in range(count):
                engine.add_ingredient("slag", emit=False)
            engine.spin()
            self.assertEqual(expected, engine.s.gold)

        duplicate = self.fresh()
        duplicate.s.items[:] = ["crowded_lab", "crowded_lab"]
        for _ in range(30):
            duplicate.add_ingredient("slag", emit=False)
        duplicate.spin()
        self.assertEqual(3, duplicate.s.gold)

    def test_monster_guide_checks_each_monster_independently_and_can_remove_multiple(self) -> None:
        engine = self.fresh()
        monsters = [engine.add_ingredient("goblin", emit=False) for _ in range(3)]
        engine.s.items.append("monster_guide")
        engine._board = list(monsters)
        engine._coords = [(0, 0), (0, 1), (0, 2)]
        engine._values = [0, 0, 0]
        draws = iter((0.10, 0.30, 0.10))
        calls: list[float] = []
        engine.r.random = lambda: calls.append(1.0) or next(draws, 0.99)
        engine._run_item_round_effects()
        self.assertEqual(1, len([x for x in engine.s.ingredients if "monster" in engine.catalog.ingredients[x.def_id].get("tags", [])]))
        self.assertEqual(2, engine.s.stats["event_counts"]["removed_tag:monster"])
        self.assertEqual(3, len(calls))

    def test_monster_already_removed_is_not_checked_again(self) -> None:
        engine = self.fresh()
        first = engine.add_ingredient("goblin", emit=False)
        second = engine.add_ingredient("goblin", emit=False)
        engine.s.items.append("monster_guide")
        engine._board = [first, second]
        engine._coords = [(0, 0), (0, 1)]
        engine._values = [0, 0]
        engine._remove(first, "removed", 0)
        calls: list[float] = []
        engine.r.random = lambda: calls.append(1.0) or 0.99
        engine._run_item_round_effects()
        self.assertEqual(1, len(calls))
        self.assertIn(second, engine.s.ingredients)

    def test_monster_guide_removal_events_trigger_essence_from_any_source(self) -> None:
        engine = self.fresh()
        monsters = [engine.add_ingredient("goblin", emit=False) for _ in range(3)]
        engine.add_essence("monster_guide_essence")
        for monster in monsters:
            self.assertTrue(engine._remove(monster, "removed", None))
        engine.check_essences()
        self.assertEqual(30, engine.s.gold)
        self.assertEqual(1, engine.s.tokens["remove"])
        self.assertIn("monster_guide_essence", engine.s.consumed_essences)

    def test_new_counter_state_has_safe_default_for_old_save(self) -> None:
        engine = self.fresh()
        old_data = engine.s.to_dict()
        old_data["stats"].pop("spawn_counters", None)
        resumed = GameEngine().bind(GameState.from_dict(old_data))
        self.assertEqual({}, resumed.s.stats["spawn_counters"])

    def test_agent_payload_exposes_new_owned_definitions_and_counters(self) -> None:
        engine = self.fresh()
        for item_id in ("ore_sorting_table", "crowded_lab", "monster_guide"):
            engine.add_item(item_id)
        engine.add_essence("monster_guide_essence")
        payload = engine.agent_payload("status")
        self.assertEqual(
            {"ore_sorting_table", "crowded_lab", "monster_guide"},
            {row["id"] for row in payload["items_detail"]},
        )
        self.assertEqual("monster_guide_essence", payload["essences_detail"][0]["id"])
        self.assertIn("spawn_counters", payload["stats"])


if __name__ == "__main__":
    unittest.main()
