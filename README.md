# 坩埚余响 · Crucible Echoes

> 想让 AI 开始玩吗？把这个项目文件夹交给一个能运行终端的 AI，然后告诉它：“请阅读 README，使用 `agent` 接口自己开一局，一直玩到胜利或失败。”

一个**可复现、可存档、数据驱动**的纯文字炼金构筑 roguelike。你会不断扩充成分池，在 4×5 实验台上结算邻接、生成、变化、移除和永久成长效果，并在有限回合内完成越来越昂贵的炼金订单。

项目不包含任何第三方游戏的美术、文本、代码或品牌素材。项目名称、规则文案与实现均为本项目内容。项目采用 [MIT License](LICENSE)。

## 特性

- 纯文字 CLI，同时支持人类交互和 AI Agent 单步操作。
- 固定 seed 与存档中的 RNG 状态保证结果可复现。
- JSON 存档，可暂停、恢复和迁移旧存档。
- 成分、道具、精粹、订单和难度规则均由 JSON 数据驱动。
- Agent 每次进程只执行一个动作，并输出统一的 `[STATE]` JSON。

## 快速开始

需要 Python 3.10 或更高版本，不依赖第三方包。

### 人类交互模式

```bash
python game.py new --seed 42 --difficulty 1
python game.py start
```

Windows PowerShell 也可以使用：

```powershell
py -3 game.py new --seed 42 --difficulty 1
py -3 game.py start
```

默认存档位于 `.saves/current.json`。如需使用其他存档，在命令末尾添加 `--save 路径.json`。

### 人类单步命令

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

相同 seed 加相同操作序列会产生相同的盘面、候选和随机触发结果。

### 批量模拟与平衡报告

无需人工操作即可运行批量对局。默认运行 1000 局，并生成 Markdown 报告和包含逐局明细的 JSON 报告：

```bash
python game.py simulate --games 1000 --seed 42 --difficulty 1
```

可用参数：

```bash
python game.py simulate \
  --games 5000 \
  --seed 42 \
  --difficulty 10 \
  --strategy heuristic-v2 \
  --summary-only \
  --report reports/difficulty10.md \
  --json-report reports/difficulty10.json
```

`--summary-only` 保留汇总、内容统计、成长曲线和池遥测，不写入逐局动作明细，适合数千局扫描。

按难度 1-5 每档 1000 局、难度 6-10 每档 500 局运行完整难度扫描：

```bash
python game.py simulate-sweep \
  --seed 424242 \
  --games-low 1000 \
  --games-high 500 \
  --report reports/balance_sweep.md \
  --json-report reports/balance_sweep.json \
  --detail-directory reports/balance_sweep
```

模拟默认使用可替换的 `heuristic-v1` 策略；另有 `heuristic-v2`，在复用同一套数据驱动评分的基础上，牌池超过20后降低普通成分接牌意愿，超过26后优先删除低留存/高占池成本成分，并在候选偏弱时更积极跳牌或 Roll。两种策略都不额外抽取 RNG，也不硬编码具体成分 ID。可用 `--strategy heuristic-v1` 或 `--strategy heuristic-v2` 选择策略。报告包含通关率、各层死亡率、金币与属性成长曲线、池来源遥测，以及普通成分、物品、装备和精粹的候选出现、选择、获取、触发/消耗和最终持有表现。疑似过强/过弱标记仅供人工复核。难度扫描还会输出 1-10 通关率曲线和相邻难度跳变。

## AI Agent 接口

`agent` 接口面向 LLM 和自动化程序。它与人类使用的 `start` 模式不同，遵循两个约定：

1. 每次进程调用只执行一个动作。
2. 每次调用后输出一行机器可读状态：

```text
[STATE] {"protocol":"crucible-echoes-agent/v1", ...}
```

建议整局始终使用同一个存档路径：

```bash
python game.py agent new --seed 42 --difficulty 1 --save .saves/agent.json
python game.py agent spin --save .saves/agent.json
python game.py agent choose 2 --save .saves/agent.json
python game.py agent status --save .saves/agent.json
```

支持的 Agent 动作：

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

状态 JSON 包含完整可观察状态以及：

- `available_actions` 和 `available_action_specs`
- 当前动作、`ok` 结果和错误信息
- 当前候选、最近盘面、日志、库存和全部定义
- 可复现 RNG 状态
- 召唤魔法等机制使用的 `spawn_counters`

Agent 应在每次操作后重新读取 `[STATE]`，只从 `available_actions` 中选择下一步，不要直接编辑存档。非法操作会返回退出码 `2`，但仍输出合法状态，并保持原存档不变。

完整协议说明见 [`docs/AGENT_INTERFACE.md`](docs/AGENT_INTERFACE.md)。

### 给 AI Agent 的提示词

> 请独立游玩《坩埚余响》。只使用 `python game.py agent ...` 接口，创建游戏后始终使用同一个 save 文件。每次命令执行后读取 `[STATE]` JSON，根据订单、金币、实验池、候选、道具、精粹、最近盘面和 `available_actions` 选择下一步。一次只执行一个动作，不要直接编辑存档，持续游玩直到胜利或失败。

## 核心循环

1. 从成分池中无放回抽取最多 20 个成分，随机铺入实验台。
2. 按九宫格邻接关系结算基础价值、加值、乘算、生成、变化、移除和其他效果。
3. 在回合结束后的候选中选择一个成分加入实验池，也可以跳过，或消耗 Roll Token 重调候选。
4. 在订单期限内获得足够金币，完成订单后支付目标金额并领取保底奖励。
5. 使用 Delete Token 精简实验池，使用 Essence Token 激活精粹的独立一次性条件效果。
6. 完成第 12 份订单即获得胜利；难度10在第12份后追加一份15回合、1350g的最终订单。

特殊成分「工程图纸」会永久扩建实验台：在第 3 列第 1 行正上方增加一个额外格，使容量从 20 提升至 21。新增格与第一行第 2、3、4 列相邻。

## 内容与数据

当前内容规模：

- 成分：144 个有稀有度的成分（1 级 45 个、2 级 55 个、3 级 34 个、4 级 10 个），另有特殊成分「废渣」1 个，合计 145 个
- 道具：115 个（1 级 48 个、2 级 32 个、3 级 23 个、4 级 12 个）
- 精粹：106 个独立条件效果
- 难度：10 级累计规则

数据文件位于 `src/crucible_echoes/data/`：

- `ingredients.json`：稀有度、基础价值、标签、权重和成分效果
- `items.json`：常驻、周期、事件和主动道具
- `essences.json`：独立触发条件和一次性效果
- `progression.json`：概率表、订单曲线、初始池和难度参数

最近的平衡扩展包括选矿台、拥挤实验室、怪物指南及其精粹；矿脉和召唤魔法加入了生成保底规则；不可能容器精粹的奖励调整为 75g。当前平衡值还包括：棕色试剂每累计 2 个新成分获得 3g，猫砂盆每移除一只猫获得 6g，黄金幸运核心稀有度倍率为 ×3；双倍账本、工具腰带、试剂架的卡牌稀有度分别上调一级；魔法滤网使负面魔法不再触发负面效果，分类垃圾桶的目标移除奖励为 8g，蓝色试剂的触发奖励为 4g。不可能容器在成分池超过 30 个后才开始提供收益，且每回合上限为 10g。选矿台对所有矿物生成提供至少2级保证；幸运魔药连续保障两次成分选择；纸张的永久成长概率为30%；小保险箱每次获得Token奖励4g；备用钥匙每次打开箱子额外获得4g；魔法魔法基础价值为2g。难度4只降低删除与Roll奖励，难度10的精粹奖励为1个并追加最终订单。新增状态字段会在加载旧存档时使用安全默认值。

新增构筑内容包括备用烧杯、旧账本、废纸箱、储蓄罐、动物/人类名册、棱镜底座、纸镇、燃料储罐、三格余量、砂纸盒、彩蛋盒、旧目录、物资订阅与魔药催化器。动物/人类名册产生的候选会在抽取阶段严格按标签过滤；砂纸盒和彩蛋盒可在没有待处理选择时用 `use ITEM_ID` 自愿兑换。旧目录的跳过奖励可以累计，并在下一组成分选择中一次性消耗。储蓄罐的储藏金额与定向候选的标签限制都写入 JSON 存档，并通过 Agent 状态公开。

完整冻结规则见 [`docs/SPEC.md`](docs/SPEC.md)。

## 机器可读输出

普通命令的输出末尾也会附带：

```text
[STATE] { ...JSON... }
```

需要严格的一次一动作接口时，请使用 `agent` 命令；脚本不需要解析人类可读文本。

## 测试

运行完整测试套件：

```bash
python run_tests.py
```

测试覆盖概率与稀有度、seed/RNG 复现、邻接与扩建、永久加值、变化/移除/生成、订单、Token、精粹、累计难度、长局稳定性，以及最近新增的生成保底、池大小条件和怪物移除机制。

## 项目结构

```text
game.py                         零安装入口
src/crucible_echoes/cli.py      CLI、人类交互模式与 Agent 接口
src/crucible_echoes/engine.py   状态机、结算与事件系统
src/crucible_echoes/simulation.py 批量模拟、策略与平衡报告
src/crucible_echoes/model.py    JSON 可序列化状态
src/crucible_echoes/rng.py      可保存的确定性随机流
src/crucible_echoes/data/       数据定义
tests/                          自动测试
docs/SPEC.md                    冻结规则规格
docs/AGENT_INTERFACE.md         Agent 协议说明
LICENSE                         MIT 许可证
```

## 贡献

欢迎新增成分、道具、精粹、测试、数值平衡和自动化接口。新增机制请尽量保持数据驱动、可复现，并补充对应测试。

## Credits

Developed with assistance from **ChatGPT by OpenAI**.

Additional development and code assistance provided through **OpenAI Codex**.
