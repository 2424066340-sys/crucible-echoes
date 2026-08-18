# 坩埚余响 · Crucible Echoes

一个可复现、可存档、数据驱动的纯文字炼金构筑 roguelike。你不断扩充实验池，每回合把最多20个成分随机铺入实验台，结算邻接、消耗、变化、生成与永久成长，并在期限内完成越来越昂贵的炼金订单。

项目不包含任何第三方游戏的美术、文本、代码或品牌素材。全部名称、说明与实现均为本项目内容；MIT 许可证见 [LICENSE](LICENSE)。

## 快速开始

需要 Python 3.10 或更高版本，不依赖第三方包。

```text
python game.py new --seed 42 --difficulty 1
python game.py start
```

Windows 也可使用：

```text
py -3 game.py new --seed 42 --difficulty 1
py -3 game.py start
```

默认存档位于 `.saves/current.json`。单步命令也能直接调用：

```text
python game.py status
python game.py spin
python game.py choose 2
python game.py skip
python game.py reroll
python game.py inventory
python game.py remove 7
python game.py use large_material_pack
```

另存一局时，在命令末尾加 `--save 路径.json`。同一 seed、相同指令序列会产生相同盘面、候选和随机触发；随机数状态完整保存在 JSON 中。

## 核心循环

1. 从成分池无放回抽取最多20个成分，随机铺入4×5实验台。
2. 按九宫格邻接结算基础价值、加值、乘算、生成、变化与移除。
3. 从成分候选中选择一个加入实验池，也可以跳过或消耗 Roll Token 重调。
4. 在订单期限内攒够金额；完成订单后支付金额并获得保底成分、道具与可能的精粹选择。
5. 使用删除 Token 精简实验池；使用精粹 Token 在订单完成时获得独立的一次性条件被动。
6. 完成第12份订单即胜利。

工程图纸会在第3列第1行正上方永久加建一格，使容量变为21。新增格与第一行第2、3、4列相邻。

## 内容与数据

当前内容规模：

- 成分：45个1级、55个2级、34个3级、10个4级，以及特殊成分“废渣”。
- 道具：36个1级、31个2级、20个3级、10个4级。
- 精粹：96个独立条件效果。
- 难度：10级累计规则。

所有可扩充内容都位于 `src/crucible_echoes/data/`：

- `ingredients.json`：稀有度、基础价值、标签、权重与成分效果。
- `items.json`：常驻、周期、事件与主动道具。
- `essences.json`：独立触发条件与一次性效果。
- `progression.json`：概率表、订单曲线、初始池和难度参数。

完整冻结规格见 [docs/SPEC.md](docs/SPEC.md)。

## 机器可读输出

每个状态输出最后都带一行：

```text
[STATE] { ...JSON... }
```

因此脚本或 AI 玩家无需从排版文本猜测金币、订单、候选和最近盘面。

## 测试

```text
python run_tests.py
```

测试覆盖概率表与高阶挤压、seed复现、九宫格及扩建邻接、永久加值、变化/移除/生成、订单、Token、精粹与累计难度。

## 项目结构

```text
game.py                         零安装入口
src/crucible_echoes/cli.py      命令行和交互模式
src/crucible_echoes/engine.py   状态机、结算与事件系统
src/crucible_echoes/model.py    JSON可序列化状态
src/crucible_echoes/rng.py      可保存的确定性随机流
src/crucible_echoes/data/       数据定义
tests/                           自动测试
docs/SPEC.md                    冻结规则规格
```

欢迎新增成分、道具、精粹、测试和数值平衡修订。
