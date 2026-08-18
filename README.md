# 坩埚余响 · Crucible Echoes

一个**可复现、可存档、数据驱动**的纯文字炼金构筑 roguelike。

你将不断扩充实验池。每回合，游戏会从池中随机抽取最多 20 个成分并铺入实验台，随后结算邻接、消耗、变化、生成、永久成长等效果。你的目标是在有限回合内完成越来越昂贵的炼金订单，并最终完成第 12 份订单。

项目不包含任何第三方游戏的美术、文本、代码或品牌素材。全部名称、说明与实现均为本项目原创内容。项目采用 MIT License，详见 [LICENSE](https://github.com/2424066340-sys/crucible-echoes/blob/main/LICENSE)。

## 快速开始

需要 Python 3.10 或更高版本，不依赖第三方包。

```bash
python game.py new --seed 42 --difficulty 1
python game.py start
```

Windows 也可以使用：

```powershell
py -3 game.py new --seed 42 --difficulty 1
py -3 game.py start
```

默认存档位于：

```text
.saves/current.json
```

也可以直接使用单步命令：

```bash
python game.py status
python game.py spin
python game.py choose 2
python game.py skip
python game.py reroll
python game.py inventory
python game.py remove 7
python game.py use large_material_pack
```

如需使用其他存档，在命令末尾添加：

```text
--save 路径.json
```

同一 seed、相同指令序列会产生相同的盘面、候选与随机触发结果。随机数状态会完整保存在 JSON 存档中，因此游戏可以稳定复现。

## 核心循环

1. 从成分池中无放回抽取最多 20 个成分，随机铺入 4×5 实验台。
2. 根据九宫格邻接关系结算基础价值、加值、乘算、生成、变化、移除与其他效果。
3. 从回合结束后的成分候选中选择一个加入实验池，也可以跳过，或消耗 Roll Token 重调候选。
4. 在订单期限内获得足够金币。完成订单后支付目标金额，并获得保底成分、道具以及可能出现的精粹奖励。
5. 使用删除 Token 精简实验池；使用精粹 Token，在完成订单时获得独立的一次性条件被动。
6. 完成第 12 份订单即获得胜利。

特殊成分「工程图纸」会永久扩建实验台：在第 3 列第 1 行正上方增加一个额外格，使实验台容量从 20 提升至 21。新增格与第一行第 2、3、4 列相邻。

## AI Agent 接口

Crucible Echoes 提供专门面向 LLM 与自动化程序的 `agent` 接口。

与人类使用的 `start` 交互模式不同，`agent` 接口遵循：

**一次进程调用只执行一个动作。**

每次调用都只输出一行机器可读状态：

```text
[STATE] {"protocol":"crucible-echoes-agent/v1", ...}
```

建议 AI Agent 始终使用同一个存档路径完成整局游戏：

```bash
python game.py agent new --seed 42 --difficulty 1 --save .saves/agent.json
python game.py agent spin --save .saves/agent.json
python game.py agent choose 2 --save .saves/agent.json
python game.py agent status --save .saves/agent.json
```

支持的 Agent 动作为：

```text
new
status
spin
choose N
skip
reroll
remove N
inventory
use ITEM_ID
help
```

状态 JSON 中包含：

* 完整持久化 `GameState`
* RNG 状态
* 成分、道具与精粹定义
* 当前待选奖励
* 最近盘面与日志
* `available_actions`
* `available_action_specs`
* 当前操作结果 `ok`
* 当前操作 `action`
* 错误信息 `error`

AI 玩家无需从终端排版中猜测游戏状态，只需要读取 `[STATE]` JSON，并从 `available_actions` 中选择下一步操作。

如果操作非法，程序会返回退出码 `2`，但仍然输出合法的 `[STATE]` JSON，并保持原存档状态不变。

### 给 AI 玩家的建议

如果你是一个能够执行终端命令的 AI Agent：

1. 使用 `agent` 接口，而不是 `start`。
2. 首先运行 `agent new` 创建存档。
3. 每次操作后重新读取 `[STATE]`。
4. 只执行 `available_actions` 中允许的操作。
5. 不要直接修改存档 JSON。
6. 重复执行单步动作，直到游戏进入胜利或失败状态。

换句话说，人类负责炼金也行，AI 自己把实验室炸掉也行。项目对两种智慧形式一视同仁。

## 内容与数据

当前内容规模：

* 成分：45 个 1 级、55 个 2 级、34 个 3 级、10 个 4 级，以及特殊成分「废渣」
* 道具：36 个 1 级、31 个 2 级、20 个 3 级、10 个 4 级
* 精粹：96 个独立条件效果
* 难度：10 级累计规则

所有可扩充内容均位于：

```text
src/crucible_echoes/data/
```

其中：

* `ingredients.json`：稀有度、基础价值、标签、权重与成分效果
* `items.json`：常驻、周期、事件与主动道具
* `essences.json`：独立触发条件与一次性效果
* `progression.json`：概率表、订单曲线、初始池与难度参数

完整冻结规格见：

[docs/SPEC.md](https://github.com/2424066340-sys/crucible-echoes/blob/main/docs/SPEC.md)

## 机器可读输出

普通命令的状态输出末尾也会附带：

```text
[STATE] { ...JSON... }
```

因此脚本或 AI 玩家无需从人类可读文本中解析金币、订单、候选和最近盘面。

需要严格的一次一动作机器接口时，请使用 `agent` 命令。

## 测试

运行：

```bash
python run_tests.py
```

测试覆盖：

* 概率表与高阶稀有度挤压
* seed 与 RNG 状态复现
* 九宫格与扩建格邻接
* 永久加值
* 变化、移除与生成
* 订单系统
* Token
* 精粹
* 累计难度规则
* 长局状态稳定性

## 项目结构

```text
game.py                         零安装入口
src/crucible_echoes/cli.py      CLI、人类交互模式与 Agent 接口
src/crucible_echoes/engine.py   状态机、结算与事件系统
src/crucible_echoes/model.py    JSON 可序列化状态
src/crucible_echoes/rng.py      可保存的确定性随机流
src/crucible_echoes/data/       数据定义
tests/                          自动测试
docs/SPEC.md                    冻结规则规格
```

## 贡献

欢迎新增：

* 成分
* 道具
* 精粹
* 测试
* 数值平衡修订
* AI Agent / MCP 等自动化接口

提交内容请尽量保持数据驱动、可复现，并为新增机制补充对应测试。

## Credits

Developed with assistance from **ChatGPT by OpenAI**.

Additional development and code assistance provided through **OpenAI Codex**.

