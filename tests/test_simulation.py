from __future__ import annotations

import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from crucible_echoes.cli import main
from crucible_echoes.engine import GameEngine
from crucible_echoes.model import PendingChoice
from crucible_echoes.simulation import (
    HeuristicStrategy,
    HeuristicV2Strategy,
    run_batch,
    run_difficulty_sweep,
    simulate_game,
    strategy_from_name,
)


class SimulationTests(unittest.TestCase):
    def test_same_seed_reproduces_batch_and_strategy(self) -> None:
        first = run_batch(games=6, seed=12345, difficulty=2)
        second = run_batch(games=6, seed=12345, difficulty=2)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(HeuristicStrategy().name, first.strategy)

    def test_batch_finishes_within_action_budget(self) -> None:
        report = run_batch(games=12, seed=77, difficulty=1, max_actions=1000)
        self.assertEqual(12, len(report.games_detail))
        self.assertTrue(all(row["action_count"] <= 1000 for row in report.games_detail))
        self.assertTrue(all(row["status"] in {"won", "lost", "aborted"} for row in report.games_detail))
        self.assertEqual(0, report.summary["aborted"])

    def test_heuristic_pool_policy_uses_generic_soft_cap_and_rolls_weak_choices(self) -> None:
        engine = GameEngine()
        engine.new_game(7, difficulty=1)
        policy = HeuristicStrategy()
        engine.s.tokens["roll"] = 1
        weak = PendingChoice(kind="ingredient", offers=["oil", "oil", "oil"])
        self.assertTrue(policy.should_reroll(engine, weak))
        engine.s.tokens["remove"] = 1
        for _ in range(21):
            engine.add_ingredient("water", emit=False)
        self.assertEqual(26, len(engine.s.ingredients))
        self.assertIsNotNone(policy.removal_index(engine))
        engine.s.ingredients = engine.s.ingredients[:25]
        self.assertIsNone(policy.choose(engine, PendingChoice(kind="ingredient", offers=["oil", "oil", "oil"])))

    def test_heuristic_v2_skips_after_twenty_and_deletes_after_twenty_six(self) -> None:
        engine = GameEngine()
        engine.new_game(7, difficulty=1)
        engine.s.ingredients.clear()
        for _ in range(21):
            engine.add_ingredient("water", emit=False)
        policy = HeuristicV2Strategy()
        self.assertIsNone(policy.choose(engine, PendingChoice(kind="ingredient", offers=["oil"])))

        for _ in range(6):
            engine.add_ingredient("water", emit=False)
        engine.s.tokens["remove"] = 1
        self.assertEqual(1, policy.removal_index(engine))
        self.assertEqual("heuristic-v2", strategy_from_name("heuristic-v2").name)

    def test_heuristic_v2_batch_is_seed_reproducible(self) -> None:
        first = run_batch(games=6, seed=2468, difficulty=1, strategy=HeuristicV2Strategy())
        second = run_batch(games=6, seed=2468, difficulty=1, strategy=HeuristicV2Strategy())
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual("heuristic-v2", first.strategy)

    def test_pool_cost_uses_provenance_and_releases(self) -> None:
        engine = GameEngine()
        engine.new_game(7, difficulty=1)
        for _ in range(20):
            engine.add_ingredient("water", emit=False)
        policy = HeuristicStrategy()
        active = policy._candidate_pool_cost(engine, "water", "active_choice")
        generated = policy._candidate_pool_cost(engine, "water", "automatic_generation")
        temporary = policy._candidate_pool_cost(engine, "water", "one_time_temporary")
        self.assertGreater(active, generated)
        self.assertGreater(generated, temporary)
        self.assertLess(
            policy._candidate_pool_cost(engine, "reroll_potion", "active_choice"),
            active,
        )

    def test_build_state_and_pool_events_are_data_driven(self) -> None:
        policy = HeuristicStrategy()
        engine = GameEngine()
        engine.new_game(12, difficulty=1)
        engine.add_ingredient("vein", emit=False)
        state = policy.build_state(engine)
        self.assertIn("ore", state["tag_counts"])
        self.assertIn("ore", state["generator_tags"])

        def start_with_generator(game: GameEngine) -> None:
            game.s.ingredients.clear()
            game.add_ingredient("vein", emit=False)
            game.s.gold = 25

        record = simulate_game(12, difficulty=1, max_actions=1000, on_start=start_with_generator)
        events = record.strategy_events["pool_events"]
        self.assertTrue(any(event["source"] == "active_choice" for event in events))
        self.assertTrue(any(source in {"automatic_generation", "summon_or_periodic"} for source in record.strategy_events["pool_origin_counts"]))
        self.assertEqual(
            sum(record.strategy_events["pool_origin_counts"].values()),
            len(record.held_ingredients) + len(record.held_equipment),
        )

    def test_batch_summary_exposes_pool_provenance_telemetry(self) -> None:
        report = run_batch(games=4, seed=12, difficulty=1)
        self.assertIn("pool_origin_counts", report.summary)
        self.assertIn("pool_event_counts", report.summary)
        self.assertGreaterEqual(sum(report.summary["pool_origin_counts"].values()), 1)
        self.assertGreaterEqual(sum(report.summary["pool_event_counts"].values()), 1)

    def test_report_includes_pool_distribution_summing_to_games(self) -> None:
        report = run_batch(games=10, seed=123, difficulty=1)
        self.assertIn("average_max_pool_size", report.summary)
        self.assertEqual(10, sum(report.summary["pool_size_distribution"].values()))
        self.assertTrue(all("max_pool_size" in row["final_attributes"] for row in report.games_detail))

    def test_simulated_state_has_no_negative_or_out_of_range_values(self) -> None:
        report = run_batch(games=12, seed=88, difficulty=10)
        for row in report.games_detail:
            self.assertGreaterEqual(row["gold"], 0)
            self.assertGreaterEqual(row["end_layer"], 1)
            self.assertLessEqual(row["end_layer"], 13)
            self.assertTrue(all(value >= 0 for value in row["final_attributes"]["tokens"].values()))
            self.assertNotIn("state_invariant:", row.get("error") or "")

    def test_gold_floor_prevents_negative_state_from_negative_effects(self) -> None:
        engine = GameEngine()
        engine.new_game(123, difficulty=1)
        engine.s.gold = 0
        engine._gain_gold(-5, "测试扣款")
        self.assertEqual(0, engine.s.gold)

    def test_report_counts_match_requested_games_and_content_stats(self) -> None:
        games = 15
        report = run_batch(games=games, seed=99, difficulty=1)
        self.assertEqual(games, report.summary["games_requested"])
        self.assertEqual(games, report.summary["games_recorded"])
        self.assertEqual(
            games,
            report.summary["wins"] + report.summary["losses"] + report.summary["aborted"],
        )
        for category in ("items", "ingredients", "equipment", "essences"):
            for row in report.content[category]:
                self.assertLessEqual(row["final_owned_games"], games)
                self.assertGreaterEqual(row["offer_count"], row["choice_count"])
                self.assertGreaterEqual(row["acquisition_count"], row["choice_count"])
        self.assertTrue(all(point["samples"] <= games for point in report.growth_curve))
        self.assertIn("ingredients", report.content)
        self.assertTrue(any(row["id"] == "water" for row in report.content["ingredients"]))

    def test_large_scan_can_drop_per_game_details_but_keep_summary(self) -> None:
        report = run_batch(games=4, seed=101, difficulty=1, retain_details=False)
        self.assertEqual(4, report.summary["games_recorded"])
        self.assertEqual([], report.games_detail)
        self.assertGreaterEqual(report.summary["average_rolls"], 0.0)
        self.assertGreaterEqual(report.summary["average_deletes"], 0.0)

    def test_simulate_cli_writes_human_and_json_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            markdown = Path(directory) / "balance.md"
            payload = Path(directory) / "balance.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "simulate",
                        "--games",
                        "2",
                        "--seed",
                        "7",
                        "--report",
                        str(markdown),
                        "--json-report",
                        str(payload),
                    ]
                )
            self.assertEqual(0, code)
            self.assertTrue(markdown.exists())
            self.assertTrue(payload.exists())
            data = json.loads(payload.read_text(encoding="utf-8"))
            self.assertEqual(2, data["summary"]["games_recorded"])
            self.assertIn("ingredients", data["content"])
            self.assertIn("### 成分", markdown.read_text(encoding="utf-8"))
            self.assertIn("自动标记的疑似平衡异常", markdown.read_text(encoding="utf-8"))

    def test_simulate_cli_accepts_heuristic_v2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([
                    "simulate",
                    "--games", "1",
                    "--seed", "7",
                    "--strategy", "heuristic-v2",
                    "--summary-only",
                    "--report", str(root / "v2.md"),
                    "--json-report", str(root / "v2.json"),
                ])
            self.assertEqual(0, code)
            data = json.loads((root / "v2.json").read_text(encoding="utf-8"))
            self.assertEqual("heuristic-v2", data["config"]["strategy"])
            self.assertEqual([], data["games"])

    def test_single_game_can_use_replacement_strategy(self) -> None:
        class FirstOfferStrategy(HeuristicStrategy):
            name = "first-offer-test"

            def choose(self, engine, choice):
                return 1 if choice.offers else None

        record = simulate_game(42, strategy=FirstOfferStrategy(), max_actions=1000)
        self.assertEqual("first-offer-test", FirstOfferStrategy.name)
        self.assertLessEqual(record.action_count, 1000)

    def test_simulate_game_on_start_hook_runs_before_first_spin(self) -> None:
        seen: list[tuple[int, str]] = []

        def on_start(engine: GameEngine) -> None:
            engine.s.items.append("ore_sorting_table")
            seen.append((engine.s.spin, engine.s.items[-1]))

        record = simulate_game(42, on_start=on_start, max_actions=1000)
        self.assertEqual([(0, "ore_sorting_table")], seen)
        self.assertLessEqual(record.action_count, 1000)

    def test_content_report_includes_trigger_and_consumption_telemetry(self) -> None:
        report = run_batch(games=8, seed=123, difficulty=1)
        row = next(item for item in report.content["items"] if item["id"] == "brown_reagent")
        for key in (
            "trigger_count",
            "triggered_games",
            "win_rate_when_triggered",
            "consumed_count",
            "consumed_games",
            "win_rate_when_consumed",
        ):
            self.assertIn(key, row)

    def test_content_report_includes_normal_ingredient_telemetry(self) -> None:
        report = run_batch(games=8, seed=456, difficulty=1)
        self.assertIn("ingredients", report.content)
        row = next(item for item in report.content["ingredients"] if item["id"] == "water")
        self.assertGreaterEqual(row["acquisition_count"], 1)
        self.assertGreaterEqual(row["final_owned_games"], 0)
        self.assertIn("win_rate_when_owned", row)
        self.assertTrue(all("held_ingredients" in game for game in report.games_detail))

    def test_difficulty_sweep_reports_curve_and_adjacent_jumps(self) -> None:
        sweep = run_difficulty_sweep(games_by_difficulty={1: 2, 2: 2, 3: 2}, seed=321)
        data = sweep.to_dict()
        self.assertEqual([1, 2, 3], [row["difficulty"] for row in data["win_rate_curve"]])
        self.assertEqual(2, data["win_rate_curve"][0]["games"])
        self.assertEqual(2, len(data["adjacent_jumps"]))
        self.assertIn("reports", data)

    def test_simulate_sweep_cli_writes_summary_and_detail_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markdown = root / "sweep.md"
            payload = root / "sweep.json"
            details = root / "details"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "simulate-sweep",
                        "--games-low",
                        "1",
                        "--games-high",
                        "1",
                        "--seed",
                        "7",
                        "--report",
                        str(markdown),
                        "--json-report",
                        str(payload),
                        "--detail-directory",
                        str(details),
                    ]
                )
            self.assertEqual(0, code)
            self.assertTrue(markdown.exists())
            self.assertTrue(payload.exists())
            self.assertEqual(10, len(json.loads(payload.read_text(encoding="utf-8"))["win_rate_curve"]))
            self.assertTrue((details / "balance_d10.json").exists())


if __name__ == "__main__":
    unittest.main()
