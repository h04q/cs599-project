# CodeSentinel — 智能代码审查与 Bug 修复 Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Built_with-LangGraph-purple)](https://github.com/langchain-ai/langgraph)

## 项目简介

一句话：**给定一个代码仓库或单文件，由多 Agent 协作完成多维度审查（Bug/安全/性能/风格）→ 对抗式验证去除误报 → 自动生成修复 Patch → 输出结构化报告。**

CodeSentinel 是 CS599 期末大作业，目标是把"代码审查"这件高频但耗时的工程实践从"人盯代码"升级为"Agent 编排"。它演示了一条完整的 SDD（规格驱动开发）+ Agentic AI 工程闭环：从 Spec 文档 → 状态机设计 → 工具定义 → LangGraph 实现 → 评估与可观测性。

## 方向

**方向一：Agentic AI 原生开发**
参考项目类型：`软件工程师 Agent`（OpenClaw / SWE-bench 同类）

## 技术栈

- **AI IDE**：Trae CN
- **LLM**：DeepSeek API（OpenAI 兼容协议，支持切换至 Anthropic / Ollama 本地）
- **Agent 框架**：LangGraph（StateGraph + 条件路由 + 检查点）
- **协议**：Function Calling、MCP（可选外挂）
- **存储**：SQLite（记忆/缓存）、本地 FAISS 向量库（历史模式）
- **可观测**：结构化 JSON 日志 + LangSmith Tracing（可选）
- **容器**：Docker + docker-compose
- **测试**：pytest

## 目录结构

```
cs599-project/
├── docs/                          # 项目文档
│   ├── CS599_大作业报告.pdf        # 最终报告（带导航目录）
│   ├── architecture.md            # 架构详细说明
│   ├── spec_product.md            # 产品规格（SDD 核心）
│   ├── spec_architecture.md       # 架构规格
│   └── spec_api.md                # API/工具规格
├── src/
│   ├── main.py                    # CLI 入口
│   ├── config/                    # 配置加载（环境变量、模型路由）
│   ├── agent/                     # 各 Agent 节点：scanner/reviewer/verifier/fixer/reporter
│   ├── tools/                     # 工具集：文件/代码静态分析/Git 操作
│   ├── graph/                     # LangGraph 状态机定义与编排
│   └── observability/             # 日志、Tracing、记忆机制
├── tests/                         # 单元/集成测试
├── examples/                      # 示例：故意写错的代码片段
├── Dockerfile / docker-compose.yml
├── requirements.txt
├── .env.example                   # 环境变量模板（不要硬编码 API Key）
├── README.md
├── LICENSE                        # MIT
└── .gitignore
```

## 环境搭建

### 1. 依赖安装

```bash
# Python 3.11+
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 环境变量配置（⚠️ 不硬编码 API Key）

```bash
cp .env.example .env
# 编辑 .env，填入：
#   DEEPSEEK_API_KEY=sk-xxxx
#   LLM_PROVIDER=deepseek          # 或 anthropic / ollama
#   LANGSMITH_API_KEY=...          # 可选，开启 tracing
```

### 3. 启动步骤

```bash
# 审查单文件
python -m src.main review --path examples/sample_buggy.py

# 审查整个目录
python -m src.main review --path ./your_repo --output report.md

# Docker 方式
docker compose up --build
```

## 项目状态

- [x] Proposal（设计文档、架构图、Spec 初稿）
- [x] MVP（核心闭环 Demo，tag: v0.1）
- [ ] Final（完整文档 + 评估 + 演示视频）

## 引用与致谢

- LangGraph：https://github.com/langchain-ai/langgraph
- SWE-bench 任务格式参考：https://www.swebench.com/
- DeepSeek API：https://platform.deepseek.com/

外部代码引用：本项目工具部分调用了 `pylint`、`bandit`、`radon` 等开源静态分析器，仅作为子进程使用；未直接复制其源码。

## 学术声明

本仓库代码由 [姓名] 于 2026 春季学期独立完成。开源协议：MIT。
违反学术纪律者按零分处理 — 本项目接受全文查重。

## 作者

- 姓名：黄谦
- 学号：2025303044
- 专业：计算机技术 / 软件工程
- 指导教师：戚欣
