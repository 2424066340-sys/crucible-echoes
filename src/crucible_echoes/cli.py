from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from .catalog import Catalog
from .engine import GameEngine, GameError
from .save import load_game, save_game

DEFAULT_SAVE = Path(".saves/current.json")

COMMAND_HELP = """可用命令：
  new --seed N --difficulty 1..10   新开一局
  start                              进入交互模式（自动读取存档）
  status                             查看订单、金币、最近盘面和待选奖励
  spin                               旋转并结算
  choose N                           选择当前第N个候选
  skip                               跳过当前选择
  reroll                             消耗1个Roll Token重调候选
  remove N                           消耗1个删除Token移除库存第N个成分
  inventory                          查看成分、道具、精粹和Token
  use ITEM_ID                        使用主动道具
  help                               显示本帮助
  quit                               退出交互模式
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crucible-echoes", description="坩埚余响：纯文字炼金构筑 roguelike")
    sub = parser.add_subparsers(dest="command")

    new = sub.add_parser("new", help="新开一局")
    new.add_argument("--seed", type=int, default=1)
    new.add_argument("--difficulty", type=int, default=1)
    new.add_argument("--save", default=str(DEFAULT_SAVE))

    start = sub.add_parser("start", help="进入交互模式")
    start.add_argument("--seed", type=int, default=1)
    start.add_argument("--difficulty", type=int, default=1)
    start.add_argument("--save", default=str(DEFAULT_SAVE))

    for name in ("status", "spin", "skip", "reroll", "inventory", "help"):
        child = sub.add_parser(name)
        child.add_argument("--save", default=str(DEFAULT_SAVE))
    choose = sub.add_parser("choose")
    choose.add_argument("number", type=int)
    choose.add_argument("--save", default=str(DEFAULT_SAVE))
    remove = sub.add_parser("remove")
    remove.add_argument("number", type=int)
    remove.add_argument("--save", default=str(DEFAULT_SAVE))
    use = sub.add_parser("use")
    use.add_argument("item_id")
    use.add_argument("--save", default=str(DEFAULT_SAVE))
    return parser


def load_engine(path: str | Path) -> GameEngine:
    source = Path(path)
    if not source.exists():
        raise GameError(f"找不到存档：{source}；请先运行 new")
    return GameEngine().bind(load_game(source))


def render(engine: GameEngine, *, inventory: bool = False) -> str:
    state = engine.s
    payload = engine.status_payload()
    lines: list[str] = []
    amount = payload["order_amount"]
    lines.append(f"状态：{payload['status']}  金币：{payload['gold']}g  难度：{payload['difficulty']}")
    lines.append(f"订单：第{payload['order']}份 / {amount}g  剩余旋转：{payload['spins_left']}")
    lines.append(f"实验池：{payload['pool_size']}个成分  盘面容量：{payload['board_capacity']}格  seed：{payload['seed']}")
    lines.append(f"Token：Roll {state.tokens.get('roll',0)} / 删除 {state.tokens.get('remove',0)} / 精粹 {state.tokens.get('essence',0)}")
    if state.last_board:
        board = "  ".join(f"{row['slot']}:{row['name']}({row['value']:+d}g)" for row in state.last_board)
        lines.append("最近盘面：" + board)
    if state.last_log:
        lines.append("最近记录：")
        lines.extend("  " + row for row in state.last_log)
    if state.pending:
        choice = state.pending[0]
        collection = engine.catalog.ingredients if choice.kind == "ingredient" else engine.catalog.items if choice.kind == "item" else engine.catalog.essences
        lines.append(f"待选 {choice.kind}（来源：{choice.source}）：")
        for index, def_id in enumerate(choice.offers, 1):
            row = collection[def_id]
            rarity = f"{row.get('rarity')}级 " if row.get("rarity") else ""
            lines.append(f"  {index}. {row['name']} [{def_id}] — {rarity}{row.get('description','')}")
        lines.append("  可用：choose N" + (" / skip" if choice.can_skip else ""))
    if inventory:
        lines.append("成分库存：")
        for index, inst in enumerate(state.ingredients, 1):
            row = engine.catalog.ingredients[inst.def_id]
            lines.append(f"  {index}. {row['name']} [{inst.def_id}] {row.get('rarity',0)}级 基础{row.get('base',0):+d} 永久{inst.permanent_bonus:+d} 年龄{inst.age}")
        lines.append("道具：")
        lines.extend(f"  - {engine.catalog.items[x]['name']} [{x}]：{engine.catalog.items[x]['description']}" for x in state.items)
        if not state.items: lines.append("  （无）")
        lines.append("精粹：")
        lines.extend(f"  - {engine.catalog.essences[x]['name']} [{x}]：{engine.catalog.essences[x]['description']}" for x in state.essences)
        if not state.essences: lines.append("  （无）")
    lines.append("[STATE] " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines)


def execute(engine: GameEngine, command: str, args: list[str]) -> str:
    if command == "status": return render(engine)
    if command == "inventory": return render(engine, inventory=True)
    if command == "help": return COMMAND_HELP
    if command == "spin": engine.spin()
    elif command == "choose": engine.choose(int(args[0]))
    elif command == "skip": engine.skip()
    elif command == "reroll": engine.reroll()
    elif command == "remove": engine.remove(int(args[0]))
    elif command == "use": engine.use_item(args[0])
    else: raise GameError(f"未知命令：{command}")
    return render(engine, inventory=command == "remove")


def interactive(save_path: Path, seed: int, difficulty: int) -> int:
    if save_path.exists():
        engine = load_engine(save_path)
        print("已读取存档。")
    else:
        engine = GameEngine(); engine.new_game(seed, difficulty); save_game(engine.s, save_path)
        print("已创建新实验。")
    print(render(engine)); print(COMMAND_HELP)
    while True:
        try:
            raw = input("炼金> ").strip()
        except EOFError:
            print()
            break
        if not raw: continue
        parts = shlex.split(raw)
        if parts[0] in {"quit", "exit", "退出"}: break
        try:
            text = execute(engine, parts[0], parts[1:])
            save_game(engine.s, save_path)
            print(text)
        except (GameError, ValueError, IndexError) as exc:
            print(f"错误：{exc}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    command = ns.command or "start"
    save_path = Path(getattr(ns, "save", DEFAULT_SAVE))
    try:
        if command == "new":
            engine = GameEngine(); engine.new_game(ns.seed, ns.difficulty); save_game(engine.s, save_path)
            print(render(engine)); return 0
        if command == "start": return interactive(save_path, getattr(ns, "seed", 1), getattr(ns, "difficulty", 1))
        if command == "help": print(COMMAND_HELP); return 0
        engine = load_engine(save_path)
        args: list[str] = []
        if command in {"choose", "remove"}: args = [str(ns.number)]
        elif command == "use": args = [ns.item_id]
        print(execute(engine, command, args))
        save_game(engine.s, save_path)
        return 0
    except GameError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
