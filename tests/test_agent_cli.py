from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from crucible_echoes.cli import main
from crucible_echoes.engine import GameEngine
from crucible_echoes.save import load_game


class AgentCliTests(unittest.TestCase):
    def call_agent(self, save: Path, *args: str) -> tuple[int, dict]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["agent", *args, "--save", str(save)])
        lines = [line for line in output.getvalue().splitlines() if line]
        self.assertEqual(len(lines), 1, output.getvalue())
        self.assertTrue(lines[0].startswith("[STATE] "), lines[0])
        return code, json.loads(lines[0][len("[STATE] "):])

    def test_agent_is_one_step_and_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            save = Path(directory) / "agent.json"
            code, state = self.call_agent(save, "new", "--seed", "42", "--difficulty", "1")
            self.assertEqual(code, 0)
            self.assertEqual(state["protocol"], "crucible-echoes-agent/v1")
            self.assertTrue(state["ok"])
            self.assertEqual(state["action"], "new")
            self.assertIn("spin", state["available_actions"])
            self.assertIn("state", state)
            self.assertEqual(len(state["ingredients"]), 5)
            self.assertEqual(state["pending_choices"], [])

            code, state = self.call_agent(save, "spin")
            self.assertEqual(code, 0)
            self.assertEqual(state["spin"], 1)
            self.assertEqual(state["action"], "spin")
            self.assertEqual(len(state["pending_choices"]), 1)
            self.assertEqual(state["available_actions"][:2], ["status", "inventory"])
            self.assertTrue(any(action.startswith("choose ") for action in state["available_actions"]))
            self.assertEqual(load_game(save).spin, 1)

            code, state = self.call_agent(save, "choose", "1")
            self.assertEqual(code, 0)
            self.assertEqual(state["action"], "choose")
            self.assertEqual(state["pending_choices"], [])
            self.assertEqual(load_game(save).spin, 1)

    def test_invalid_agent_action_still_returns_state_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            save = Path(directory) / "agent.json"
            self.call_agent(save, "new", "--seed", "9")
            self.call_agent(save, "spin")
            code, state = self.call_agent(save, "choose", "999")
            self.assertEqual(code, 2)
            self.assertFalse(state["ok"])
            self.assertEqual(state["error"]["type"], "GameError")
            self.assertEqual(state["state"]["spin"], 1)

    def test_agent_save_resume_keeps_rng_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            save = Path(directory) / "agent.json"
            self.call_agent(save, "new", "--seed", "314159")
            self.call_agent(save, "spin")
            self.call_agent(save, "skip")
            self.call_agent(save, "spin")

            direct = GameEngine()
            direct.new_game(314159)
            direct.spin()
            direct.skip()
            direct.spin()
            resumed = load_game(save)
            self.assertEqual(resumed.last_board, direct.s.last_board)
            self.assertEqual(resumed.pending[0].offers, direct.s.pending[0].offers)
            self.assertEqual(resumed.rng_state, direct.s.rng_state)


if __name__ == "__main__":
    unittest.main()
