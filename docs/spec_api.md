# API Spec — CodeSentinel

> SDD 规格族之三：**API 规格**。
> 同时覆盖三类接口：
> 1. **CLI 命令**（用户视角）
> 2. **Agent 工具集**（LLM 视角，Function Calling）
> 3. **核心数据结构**（节点之间）

---

## 1. CLI 接口

### 1.1 `review` — 执行审查

```bash
python -m src.main review [OPTIONS]
```

| 参数 | 简写 | 必需 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `--path` | `-p` | 是 | — | 待审查的文件或目录 |
| `--output` | `-o` | 否 | `report.md` | 报告输出路径 |
| `--max-rounds` | — | 否 | 0（用 .env） | reviewer↔verifier 最大轮次 |
| `--no-fix` | — | 否 | False | 禁用 Fixer，仅审查 |

**退出码**：
| code | 含义 |
| --- | --- |
| 0 | 成功（包括"没发现问题"） |
| 2 | 路径不存在 |
| 3 | LLM 配置缺失 |
| 4 | 任意节点抛出未捕获异常 |

**示例**：
```bash
# 单文件 + JSON 日志
LOG_FORMAT=json python -m src.main review -p examples/sample_buggy.py

# 整个目录，最多 3 轮，禁用修复
python -m src.main review -p ./your_repo --max-rounds 3 --no-fix
```

### 1.2 `info` — 查看当前配置

```bash
python -m src.main info
```

输出（不会暴露 API Key 值，仅显示是否已配置）：
```
LLM Provider     deepseek
Provider 已配置  ✓
最大轮次         2
启用自动修复     ✓
严重度阈值       medium
日志格式         json
```

---

## 2. Agent 工具（Function Calling）

下表列出所有暴露给 LLM 的工具。每个工具都做了**workspace 沙箱**保护，
路径越界会抛 `ValueError` 终止本次工具调用（但不中断整条链路）。

### 2.1 文件系统工具（`src/tools/fs.py`）

#### `list_files(subdir: str = ".", max_items: int = 200) -> str`
列出 workspace 下的源代码文件（按 TEXT_EXTENSIONS 过滤）。
- 自动跳过 `node_modules / .git / .venv / venv / __pycache__ / dist / build`。
- 返回换行分隔的相对路径，超过 `max_items` 截断。

#### `read_file(path: str, start_line: int = 1, end_line: int = 0) -> str`
读取文件内容并加行号。
- `end_line=0` 表示读到文件末尾。
- 文件 > 200KB 时返回 WARN 而非内容（防 token 爆炸）。

#### `write_patch(path: str, new_content: str) -> str`
覆盖写入文件。
- 自动创建父目录。
- 仅在 `enable_auto_fix=true` 时由 Fixer 调用。

### 2.2 静态分析工具（`src/tools/analyzers.py`）

| 工具 | 行为 | 输出格式 |
| --- | --- | --- |
| `run_pylint(path)` | 跑 pylint -f json，截断为前 30 条 | `{"total": N, "issues": [...]}` |
| `run_bandit(path)` | 跑 bandit -f json -q -r | `{"total": N, "issues": [...]}` |
| `run_radon(path)` | 圈复杂度，仅返回 ≥C 级 | `{"hotspots": [...], "total_files": N}` |

**通用约束**：超时 30s；工具不存在时返回 `[SKIP]` 而非异常。

### 2.3 Git 工具（`src/tools/git.py`，只读）

| 工具 | 用途 |
| --- | --- |
| `git_diff(rev="HEAD")` | 获取相对某 revision 的 diff（最多 8000 字节） |
| `git_log(limit=10)` | 最近 N 条提交 oneline |

> 故意不暴露 `git commit` / `git push` —— 修复以工作区写入为准，提交动作由人决策。

---

## 3. 核心数据结构

### 3.1 `Finding`

```python
@dataclass(slots=True)
class Finding:
    file: str                # 相对 workspace
    line: int                # 1-based
    category: Literal["bug", "security", "performance", "style"]
    severity: Literal["low", "medium", "high"]
    title: str               # 简短标题，用作 dedupe key 一部分
    detail: str              # 为什么是问题（≤ 2 句）
    suggestion: str = ""     # 怎么改（≤ 2 句）
    confirmed: bool | None = None     # Verifier 设置
    verifier_note: str = ""           # Verifier 设置
    fix_patch: str = ""               # Fixer 设置（已写入摘要）
```

**Dedupe key**：`(file, line, title)`。

### 3.2 `ReviewState`

LangGraph TypedDict（`total=False`），见 `architecture.md` §6 详细字段表。

### 3.3 LLM JSON 协议

#### Reviewer 期望的 LLM 输出
```json
[
  {
    "file": "a.py",
    "line": 10,
    "severity": "high",
    "title": "hardcoded-api-key",
    "detail": "API_KEY 字符串字面量直接暴露在源码中",
    "suggestion": "改为读取 os.environ['API_KEY']"
  }
]
```

#### Verifier 期望的 LLM 输出
```json
[
  {"index": 0, "confirmed": true,  "note": "确为硬编码密钥，无歧义"},
  {"index": 1, "confirmed": false, "note": "属于风格争议，不视为问题"}
]
```

#### Fixer 期望的 LLM 输出
```json
{
  "new_content": "完整修复后的文件内容（含原有注释和缩进）",
  "fix_strategy": "改用 os.environ 读取密钥，并添加默认值校验"
}
```

---

## 4. 配置（环境变量）

完整列表见 `.env.example`。关键项：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LLM_PROVIDER` | deepseek | deepseek/anthropic/openai/ollama |
| `DEEPSEEK_API_KEY` | — | DeepSeek 密钥（推荐） |
| `MAX_REVIEW_ROUNDS` | 2 | reviewer↔verifier 最大轮次 |
| `ENABLE_AUTO_FIX` | true | 是否调用 Fixer |
| `LOG_LEVEL` | INFO | DEBUG/INFO/WARNING/ERROR |
| `LOG_FORMAT` | json | json / text |
| `LANGSMITH_TRACING` | false | 启用 LangSmith Tracing |

---

## 5. 错误协议

所有节点遵循"**fail-soft**"约定：

| 失败级别 | 行为 |
| --- | --- |
| 工具返回 `[SKIP]` / `[TIMEOUT]` | 当作普通字符串拼进 prompt，链路继续 |
| LLM JSON 解析失败 | `_extract_json` 返回 None，节点输出 WARN 日志，无新 finding |
| 节点内部异常 | try/except 捕获，写入 `state.error`，跳到 reporter 输出已有结果 |
| LLM 配置缺失 | `LLMConfigError` 立即终止（exit code 3） |

报告中始终保留 "Verifier 未给出意见，保守保留" 这种**降级文案**，让用户能识别出 Agent 在哪里"摸不准"。
