from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from crucible_echoes.cli import main
from crucible_echoes.engine import GameEngine
from crucible_echoes.save import load_game, save_game


class EndlessModeTests(unittest.TestCase):
    @staticmethod
    def finish_rewards(engine: GameEngine, mode_choice: int | None = None) -> None:
        """Resolve all ordinary rewards, optionally resolving the mode prompt."""
        while engine.s.pending:
            if engine.s.pending[0].kind == "run_end":
                if mode_choice is None:
                    raise AssertionError("unexpected mode prompt")
                engine.choose(mode_choice)
            else:
                engine.choose(1)

    def mainline_ready(self, difficulty: int = 1) -> GameEngine:
        engine = GameEngine()
        engine.new_game(90210, difficulty=difficulty)
        engine.s.order_index = 11
        engine.s.spins_left = 1
        engine.s.gold = 1_000_000
        engine.spin()
        return engine

    def test_completion_prompts_end_or_endless_and_end_choice_wins(self) -> None:
        engine = self.mainline_ready()
        self.assertEqual("playing", engine.s.status)
        self.assertEqual("run_end", engine.s.pending[-1].kind)
        self.finish_rewards(engine, mode_choice=1)
        self.assertEqual("won", engine.s.status)
        self.assertFalse(engine.s.endless_mode)

    def test_d10_prompts_only_after_the_extra_thirteenth_order(self) -> None:
        engine = self.mainline_ready(difficulty=10)
        self.assertEqual(12, engine.s.order_index)
        self.assertFalse(any(choice.kind == "run_end" for choice in engine.s.pending))
        self.finish_rewards(engine)
        engine.s.gold = 1350
        engine.s.spins_left = 1
        engine.spin()
        self.assertEqual(13, engine.s.order_index)
        self.assertEqual("run_end", engine.s.pending[-1].kind)

    def test_enter_endless_preserves_state_and_starts_order_one(self) -> None:
        engine = self.mainline_ready()
        engine.add_item("old_ledger")
        ingredient_ids = [instance.def_id for instance in engine.s.ingredients]
        self.finish_rewards(engine, mode_choice=2)
        self.assertEqual("playing", engine.s.status)
        self.assertTrue(engine.s.endless_mode)
        self.assertEqual(1, engine.s.endless_order)
        self.assertEqual(1000, engine.s.endless_target)
        self.assertEqual(10, engine.s.spins_left)
        self.assertEqual(12, engine.s.order_index)
        self.assertTrue(set(ingredient_ids).issubset({instance.def_id for instance in engine.s.ingredients}))
        self.assertIn("old_ledger", engine.s.items)

    def test_endless_targets_use_ceiling_and_always_ten_rounds(self) -> None:
        engine = self.mainline_ready()
        self.finish_rewards(engine, mode_choice=2)
        expected = [1000, 1500, 2250, 3375, 5063, 7595]
        for target in expected[:-1]:
            self.assertEqual(target, engine.s.endless_target)
            self.assertEqual(10, engine.s.spins_left)
            engine.s.gold = target
            engine._settle_order()
            self.finish_rewards(engine)
        self.assertEqual(expected[-1], engine.s.endless_target)
        self.assertEqual(5, engine.s.stats["endless_orders_completed"])
        self.assertEqual(6, engine.s.stats["highest_endless_order"])

    def test_endless_failure_sets_lost(self) -> None:
        engine = self.mainline_ready()
        self.finish_rewards(engine, mode_choice=2)
        engine.s.ingredients.clear()
        engine.s.gold = 0
        engine.s.spins_left = 1
        engine.spin()
        self.assertEqual("lost", engine.s.status)
        self.assertTrue(engine.s.endless_mode)
        self.assertEqual(1, engine.s.endless_order)

    def test_endless_state_save_round_trip_and_legacy_defaults(self) -> None:
        engine = self.mainline_ready()
        self.finish_rewards(engine, mode_choice=2)
        engine.s.stats["highest_endless_single_turn_gold"] = 123
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endless.json"
            save_game(engine.s, path)
            restored = GameEngine().bind(load_game(path))
            self.assertEqual(engine.s.to_dict(), restored.s.to_dict())

        legacy = engine.s.to_dict()
        legacy.pop("endless_mode")
        legacy.pop("endless_order")
        legacy.pop("endless_target")
        for key in (
            "endless_orders_completed",
            "highest_endless_order",
            "highest_endless_single_turn_gold",
            "highest_single_turn_gold",
        ):
            legacy["stats"].pop(key, None)
        restored_legacy = GameEngine().bind(type(engine.s).from_dict(legacy))
        self.assertFalse(restored_legacy.s.endless_mode)
        self.assertEqual(0, restored_legacy.s.endless_order)
        self.assertEqual(0, restored_legacy.s.endless_target)
        self.assertEqual(0, restored_legacy.s.stats["highest_endless_order"])

    def test_agent_can_select_endless_mode_from_persisted_prompt(self) -> None:
        engine = self.mainline_ready()
        while len(engine.s.pending) > 1:
            engine.choose(1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.json"
            save_game(engine.s, path)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["agent", "choose", "2", "--save", str(path)])
            self.assertEqual(0, code)
            payload = json.loads(output.getvalue().strip()[len("[STATE] "):])
            self.assertTrue(payload["endless_mode"])
            self.assertEqual(1000, payload["endless_target"])
            self.assertIn("spin", payload["available_actions"])
            state = load_game(path)
            self.assertTrue(state.endless_mode)
            self.assertEqual(1000, state.endless_target)


if __name__ == "__main__":
    unittest.main()
