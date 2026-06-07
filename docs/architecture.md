# Architecture — 详细架构说明（图文版）

> 这份文档是 **架构 Spec** 的图文化版本，用于答辩展示。要点是"少量文字、一图胜千言"。

## 1. 核心架构图

```mermaid
flowchart TB
  classDef mod fill:#eef,stroke:#557,stroke-width:1px;
  classDef llm fill:#fef6dd,stroke:#cc9933,stroke-width:1px;
  classDef ext fill:#eafbe7,stroke:#3a8,stroke-width:1px;

  subgraph CLI["CLI 层"]
    direction LR
    main["src/main.py<br/>typer + rich"]:::mod
  end

  subgraph Graph["编排层 (LangGraph)"]
    direction TB
    SC[Scanner]:::mod
    RV[Reviewer × 4 维度]:::mod
    VF{Verifier<br/>对抗式}:::mod
    FX[Fixer]:::mod
    RP[Reporter]:::mod
    SC --> RV --> VF
    VF -->|loop| RV
    VF --> FX --> RP
  end

  subgraph Tools["工具层 (Function Calling)"]
    fs["fs.py<br/>list_files / read_file / write_patch"]:::mod
    an["analyzers.py<br/>pylint / bandit / radon"]:::mod
    git["git.py<br/>diff / log"]:::mod
  end

  subgraph Infra["基础设施"]
    cfg["Settings<br/>(.env, pydantic)"]:::mod
    logx["structlog<br/>JSON 日志"]:::mod
    mem[("SQLite<br/>memory.sqlite3")]:::mod
  end

  LLM[("DeepSeek / Anthropic /<br/>OpenAI / Ollama")]:::llm
  LS[("LangSmith<br/>(可选 Tracing)")]:::ext

  main --> Graph
  RV --> LLM
  VF --> LLM
  FX --> LLM
  Graph --> Tools
  Graph --> Infra
  Graph -.tracing.-> LS
  FX --> mem
```

## 2. Agent 状态机（详细版）

```mermaid
stateDiagram-v2
  [*] --> Scanner
  Scanner --> Reviewer: target_files
  Reviewer --> Verifier: findings(confirmed=None)
  Verifier --> Reviewer: pending && round < max
  Verifier --> Fixer: 验证完毕
  Fixer --> Reporter: 写入 patch
  Reporter --> [*]: report.md
```

## 3. 数据流与 token 预算

| 阶段 | 主要 token 消耗 | 控制手段 |
| --- | --- | --- |
| Scanner | 0（不调 LLM） | — |
| Reviewer | 文件全文 × 4 维度 | 单次 ≤ 8KB；超大文件触发 WARN |
| Verifier | 待验证 finding × 上下文片段 | 上下文窗口 ±6 行 |
| Fixer | 单条 finding × 文件全文 | 仅对 confirmed=True 调用 |
| Reporter | 0 | — |

## 4. 工具调用清单

| 工具名 | 用途 | 谁会调 |
| --- | --- | --- |
| `list_files` | 枚举文件 | Scanner |
| `read_file` | 读片段 | LLM 主动按需 |
| `write_patch` | 落盘修复 | Fixer |
| `run_pylint` | Lint | Scanner |
| `run_bandit` | 安全扫描 | Scanner |
| `run_radon` | 圈复杂度 | Scanner |
| `git_diff` | 增量审查 | LLM 主动按需 |
| `git_log` | 历史上下文 | LLM 主动按需 |

## 5. 失败回退路径

```mermaid
flowchart LR
  E1[LLM JSON 解析失败] --> S1[INFO 日志 + 跳过本批]
  E2[工具未安装/超时] --> S2[标记 SKIP/TIMEOUT, 继续]
  E3[文件 > 200KB] --> S3[WARN, 仅静态分析结论]
  E4[节点抛异常] --> S4[写 state.error, 跳到 Reporter]
  E5[LLM 配置缺失] --> S5[退出码 3]
```
