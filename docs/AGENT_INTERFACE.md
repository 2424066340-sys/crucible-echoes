# Agent interface

The `agent` command is a stateless, one-action-per-process interface for an
LLM or other automation. The human-oriented `start` command is unchanged.

Every invocation prints exactly one line with this shape:

```text
[STATE] {"protocol":"crucible-echoes-agent/v1", ...}
```

The JSON envelope contains:

- `state`: the complete persisted `GameState`, including the RNG state used to
  resume the deterministic stream;
- `ingredients`, `items_detail`, `essences_detail`: owned definitions and
  instance metadata;
- `pending_choices`: the complete reward queue, including offer definitions;
- `last_board` and `last_log`: the most recent observable result;
- `available_actions`: executable command strings for the next step;
- `available_action_specs`: the same actions in structured form;
- `ok`, `action`, and `error`: the result of the just-completed operation.

## One-step usage

Use one persistent save path for the whole run:

```text
python game.py agent new --seed 42 --difficulty 1 --save .saves/agent.json
python game.py agent spin --save .saves/agent.json
python game.py agent choose 2 --save .saves/agent.json
python game.py agent status --save .saves/agent.json
```

Supported agent actions are `new`, `status`, `spin`, `choose N`, `skip`,
`reroll`, `remove N`, `inventory`, `use ITEM_ID`, and `help`. Mutating actions
load the save, execute one engine action, save the resulting state, and exit.
Read-only actions also emit the same state envelope.

When an action is invalid, the process returns exit code `2` but still emits a
single `[STATE]` line with `ok: false`, an error object, and the unchanged
loaded state. A missing save can only report a minimal error envelope because
there is no game state to load; the `available_actions` field then contains
`new`.
