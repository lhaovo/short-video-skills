---
name: story-deslop
version: 1.1.0
description: "网文去 AI 味。对短篇故事或正文做表达、叙事用笔、故事因果三层诊断与受控修复，保留作者文风、已定剧情和信息边界。用于 /story-deslop、去 AI 味、这篇太 AI、AI 腔、网文润色和成文文风质检。"
metadata:
  source: "https://github.com/zenstory-ai/oh-story-claudecode"
---

# story-deslop：网文去 AI 味

**文风裁决**：先读 [references/style-resolution.md](references/style-resolution.md)。当前请求优先于项目文风，项目文风优先于通用默认值。文风只改变表达，不改变事实、剧情、人物知识边界或揭露顺序。

**核心目标**：表达自然、笔墨有重心、故事有依据。诊断和改稿都必须服从调用方限定的范围。

## 执行边界

- 未限定范围的独立去味，检查表达、用笔、故事三层；每层可以没有问题。
- 用户只要检测、标注或报告时，只诊断，不改正文。
- 用户只说“去 AI 味”或“这篇太 AI 了”时，按改稿处理：表达与已有内容的详略可以直接修；缺少剧情成立条件时只给方案，不擅自新增事实。
- 保护伏笔、因果、人物选择、情绪体验、空间方向和揭露顺序。不能用新增微动作、粗话、证据、冲突或旁白解释制造“真人感”。
- 准确直写、心理活动、带立场的叙述、有功能的停顿和有效长句都可以保留。不机械套 Show/Tell、固定句长或删除比例。
- 不推断作者身份，不承诺 AIGC 检测分数。脚本命中只是定位线索，零命中不证明文本没有 AI 腔。
- 不查询或记录作者记忆。调用方传入的文风与偏好只作为自然倾向，不用来覆盖用户本次要求和故事事实。

## 当前套件中的位置

在 `short-video-flow` 中，本 skill 属于 **S1A 的最后一道内部质检**，不是新的主流程阶段：

```text
S1A 分段写作
→ 整篇审查与必要修复
→ story-deslop
→ 重建 story.md 并复扫
→ story_state.py finalize
→ G1-A
→ S1B 创建 source.story.md 快照
```

- 必须发生在 S1B 创建短剧故事快照之前。
- 当前短篇项目使用 `01-故事/`，正文是 `01-故事/story.md`。
- 可选文风文件是 `01-故事/文风.md`。
- 局部白名单是 `01-故事/.deslop-whitelist`。
- 默认只自动修表达和已有内容的详略；剧情级缺口交回 `ai-novel-short-story`，不在去味阶段重新设计故事。

## Phase 1：读全文与三层扫描

先确定输入模式：

| 模式 | 输入 | 写入方式 |
|---|---|---|
| 当前短篇项目 | `01-故事/story.md`、`state.json`、`plan.md`、`segments/` | 改受影响段落，通过 `story_state.py edit-segment` 保存 |
| 独立单文件 | 用户指定的 `正文.md` 或故事文件 | 备份后修改该文件 |
| 长篇项目 | `正文/` 下的当前章节 | 本次只处理调用方指定的章节 |

通读本次范围，并读取理解所需的前文、人物设定、`plan.md` 和文风文件；不整读无关全书。资料不足时只处理有依据的部分，并标明未知。

默认读取并执行以下三份方法：

| 方法 | 检查对象 |
|---|---|
| [references/expression.md](references/expression.md) | 词句、句式、声口、句段组织、模板复现 |
| [references/narrative-focus.md](references/narrative-focus.md) | 场景作用、详略、关键过程、细节功能、情绪承接 |
| [references/story-logic.md](references/story-logic.md) | 行为依据、因果、人物立场、结果、变化和知情顺序 |

限定为某一类问题时，按 [references/deslop-gates.md](references/deslop-gates.md) 只加载相关方法。需要定位具体词句时再查 [references/banned-words.md](references/banned-words.md)。

确定性预检只报告，不改写。命令从本 skill 根目录执行，正文参数使用绝对路径：

```bash
node scripts/check-ai-patterns.js --check --fail-on=blocking <正文文件>
node scripts/check-degeneration.js --check --fail-on=blocking <正文文件>
```

退出码 `1` 表示有 blocking，`2` 表示命令或文件错误。blocking 必须按语境修净，或按项目文风登记白名单；advisory 只作提示，不为归零机械改稿。

## Phase 2：定位问题与确定改法

每个实际问题记录：

- 可定位的原文；
- 读者实际损失了什么；
- 缺的是表达、详略，还是故事成立条件；
- 最小改法和会影响的后文。

三种处置必须分开：

1. **可直接修复**：改词句、恢复已有承接、调整已定内容的详略。
2. **需要设计授权**：改变事件、动机、结果、人物所知、伏笔或揭露顺序。
3. **资料不足**：只指出未知，不替作者猜答案。

先判断故事是否成立，再判断场景篇幅，最后处理词句。不要用表层命中数决定是否检查后两层。

## Phase 3：按授权改稿

改动前先备份完整正文；当前短篇项目还要把受影响的 segment 原文件一并保留，便于核对和撤回：

```text
当前短篇项目：01-故事/backups/deslop/YYYYMMDD_story.md
              01-故事/backups/deslop/YYYYMMDD_segments/NN.md
独立文件：<文件目录>/backups/deslop/YYYYMMDD_<原文件名>
```

当前短篇项目不能直接修改 `story.md` 后当作定稿，因为 `story_state.py` 会从 `segments/` 重建正文。正确做法：

1. 对完整 `story.md` 做跨段诊断。
2. 在对应 `segments/NN.md` 上执行获准修改。
3. 用 `story_state.py edit-segment` 写回该段，提供 `content` 和更新后的 `continuity_summary`。
4. 让 `story_state.py` 重建 `story.md`。
5. 对重建后的完整正文复扫。

当前会话直接执行，不依赖外部写作角色。不能直接改 `state.json` 或已经确认的 `plan.md` 事实，也不能借新动作、新对白或新证据补足故事缺口。

写作时始终区分：

- **可以直接落改**：表达、已有承接、详略、明显笔误；
- **必须交回父流程**：新的行为依据、事件、身份、能力、证据、关系变化或结局变化。

## Phase 4：回读与复扫

对照备份、`plan.md`、前后段和授权范围回读完整场景，检查：

- 事实、人物选择、因果、情绪承接、空间方向和悬念是否保住；
- 关键过程是否仍被概述吞掉，或已恢复；
- 是否引入新的套式、微动作、剧情依据或信息泄漏；
- 对白是否仍像提纲，叙述是否只听脚本分类；
- 改写是否只把一种 AI 腔换成另一种 AI 腔。

语义改完后重新扫描：

```bash
node scripts/check-ai-patterns.js --check --fail-on=blocking <正文文件>
node scripts/check-degeneration.js --check --fail-on=blocking <正文文件>
```

退化 blocking（复读、打转、截断、占位符、工程词泄漏）必须重写受影响段。句式 blocking 要结合语境自然改写；作者明确选择的原句可登记到 `.deslop-whitelist`。

标点默认只检查，不自动落改：

```bash
node scripts/normalize-punctuation.js --check <正文文件>
```

只有用户或项目明确要求整理整份文件时，才去掉 `--check` 实际落改。省略号、破折号等允许由文风决定，不把所有停顿都换成逗号或句号。

完成一次改稿与复扫。只为新发现的具体问题继续修补，完整扫描最多三轮；达到上限仍有 blocking 时列入剩余阻塞。

## Phase 5：交付

只报告实际发生的修改，不承诺“AI 味清零”，不根据删除比例评价质量。

```md
## 改稿结果
- 表达：{改了什么；哪些有效写法保留；未检查则说明}
- 用笔：{哪里压缩、哪里展开，以及读者体验变化}
- 故事：{已恢复的承接；仍需设计或资料不足的部分}

### 代表性改动
{少量原文与改后对照}

### 尚需处理
{位置、缺口、最小设计选项及影响；没有则省略}
```

文件模式必须在对话里直接给出三层结果、少量原文/改后对照和仍未处理的项，再附修改路径；不能只回复“已处理，见文件”。交互粘贴且没有文件路径时，给改后全文。有备份时告知备份位置和能否撤回。

## 流程衔接

- S1A 内：完成后交回 `ai-novel-short-story`，重新运行 `story_state.py validate`，再 finalize。
- 接入 managed flow 时，先把完整故事与去味报告直接呈现给用户，把 G1-A 设为「等待用户确认」并结束回合；用户批准后才能 finalize 和进入 S1B。
- S1B 前：确认去味后的 `story.md` 已是最终版本，再创建短剧快照。
- 故事级缺口：交回 `ai-novel-short-story` 的整篇审查、修复或重新规划流程。
- 短剧脚本和视频提示词：不使用本 skill 自动润色；它们由 `short-story-to-drama-storyboard` 与 `short-video-prompt` 负责。
