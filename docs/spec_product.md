# Product Spec — CodeSentinel

> SDD（Spec-Driven Development）规格族之一：**产品规格**。
> 回答"做什么 / 给谁用 / 边界在哪 / 如何验收"四个问题。

| 字段 | 内容 |
| --- | --- |
| 产品代号 | CodeSentinel |
| 版本 | v0.1 (MVP) |
| 所属课程 | CS599《企业级应用软件设计与开发》2025-2026 春季 |
| 撰写日期 | 2026-06-07 |
| 文档状态 | Approved（MVP） |

---

## 1. 问题陈述

### 1.1 背景
代码评审是软件工程中价值密度最高、人工成本也最高的活动之一。
现实中存在三个长期痛点：

1. **覆盖不全**：人工 review 受时间约束，常常只看 happy path，安全/性能/复杂度类问题被漏掉。
2. **风格不一致**：不同 Reviewer 关注点不同，结论质量取决于个人经验。
3. **修复脱节**：发现问题之后，"怎么改"还要再写一份描述，沟通成本高。

现有方案（pylint / SonarQube / GitHub Code Review）能覆盖一部分静态规则，
但无法做"语义级"判断，也不能直接生成修复 patch；而单纯把 LLM 接到 IDE 里，
又往往过度报告（Hallucinated Findings），让开发者疲于应付。

### 1.2 一句话定位
**CodeSentinel 是一个 Agentic 代码审查与自动修复系统：把"扫描 → 多维度审查 → 对抗式验证 → 自动修复 → 报告"做成一条由 LangGraph 编排的工作流，让 LLM 既能利用静态分析的精确线索，又通过对抗式 Verifier 控制误报。**

### 1.3 用户与场景

| 用户 | 场景 |
| --- | --- |
| 软件工程专业研究生 | 期末作业代码自查，避免低级错误被扣分 |
| 独立开发者 | 在提交 PR 前先跑一遍 CodeSentinel，把容易暴露的 Bug 提前发现 |
| 团队 Tech Lead | 集成到 CI，对 PR 增量代码做强制审查，节省人工 |

### 1.4 非目标（Non-Goals）

- 不替代人工 review；最终是否合并由人类决定。
- 不做跨语言全栈支持；MVP 仅覆盖 Python（架构上预留多语言扩展位）。
- 不做实时 IDE 内联补全；只做"批处理式"审查。
- 不做企业 SSO / 多租户。

---

## 2. 核心用户故事

### 2.1 US-01：一键审查单文件
**作为** 学生，
**我希望** 把单个 Python 文件喂给 CodeSentinel，
**得到** 一份分类清晰、含修复建议的 Markdown 报告，
**以便** 在交作业前查漏补缺。

**验收**：
- 命令 `python -m src.main review --path foo.py` 能在 60s 内返回报告。
- 报告至少包含"安全/Bug/性能/风格"四类的小节标题，每条 finding 含 `file:line`。
- 报告的"被驳回的发现"小节能体现 Verifier 起到了过滤作用。

### 2.2 US-02：自动生成修复 Patch
**作为** 开发者，
**我希望** 系统对确认的问题直接给出可应用的修复，
**以便** 我无需手动改写大段重复样板。

**验收**：
- 默认 `enable_auto_fix=true`，命中 confirmed=true 的 finding 必产出 patch。
- Patch 写入工作区，原文件被覆盖；旧内容由 git 留底。
- 报告中标注"已写入"，并给出 fix_strategy 简述。

### 2.3 US-03：跨会话经验复用
**作为** 长期使用者，
**我希望** 系统记住"上次它怎么修这种 bug"，
**以便** 同类问题在下一个项目里被一致地处理。

**验收**：
- `.codesentinel/memory.sqlite3` 存在并可被新会话召回。
- 同样 pattern 重复触发时，Fixer 的 prompt 中能看到"历史经验"提示。

### 2.4 US-04：可观测
**作为** 课程评审老师，
**我希望** 能看到 Agent 在每一步做了什么、调用了哪些工具、消耗了多少 token，
**以便** 评估系统的工程严肃性。

**验收**：
- 默认 JSON 结构化日志输出到 stdout，每条带 `agent` / `event` / `timestamp`。
- 可选 LangSmith Tracing：`LANGSMITH_TRACING=true` 时自动接入。

---

## 3. 系统范围（Scope）

### 3.1 输入
- 单文件路径（`.py`）
- 目录路径（递归扫描，跳过 `.venv` / `node_modules` / `.git` 等）
- *（v0.2 计划）* `git diff` 范围

### 3.2 输出
- `report.md` — 主报告（默认）
- `out/findings.json` — 结构化发现（评估脚本使用）
- 工作区内被修复的文件
- stdout 的 Rich 表格（人看）

### 3.3 边界
- 仅处理 ≤ 200KB 的单文件；超过则报告 WARN 并跳过文件体读取（仍能给出基于静态分析的概要）。
- 单次运行最多审查 20 个文件（MVP 限制，避免 token 爆炸）。
- 默认 `max_review_rounds=2`，最多 reviewer ↔ verifier 来回 2 次。

---

## 4. 关键质量属性

| 属性 | 目标 |
| --- | --- |
| 正确率 | 在 `examples/sample_buggy.py` 上召回率 ≥ 80%，误报率 ≤ 30% |
| 稳定性 | 任一节点失败时整条链路不崩溃（fail-soft：转 reporter） |
| 可观测 | 每个节点至少 1 条 INFO 日志，覆盖输入规模与输出条数 |
| 安全 | 工具沙箱限制路径越界；API Key 严禁硬编码（pre-commit 检查） |
| 可扩展 | 新增审查维度只需改 `REVIEW_DIMENSIONS` 字典 |

---

## 5. 验收基线（Demo Day Checklist）

- [ ] `python -m src.main info` 能打印当前配置（不暴露 Key）。
- [ ] `python -m src.main review --path examples/sample_buggy.py` 端到端跑通。
- [ ] 报告中至少捕获 3 类问题（security、bug、performance）。
- [ ] `pytest -q` 全绿。
- [ ] Docker 镜像构建成功并可一键运行。
- [ ] LangSmith 上能看到 Trace 树（演示用）。
