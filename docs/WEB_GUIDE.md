# CodeSentinel Web 界面

## 启动 Web 服务器

```bash
# 方式 1: 使用 CLI 命令
python -m src.main web

# 方式 2: 指定端口和自动重载（开发模式）
python -m src.main web --port 8080 --reload

# 方式 3: 直接运行 Web 应用
python -m src.web.app
```

## 访问地址

- **Web 界面**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json

## API 端点

### 获取配置
```
GET /api/config
```

### 启动代码审查
```
POST /api/review
Content-Type: application/json

{
  "path": "./examples/sample_buggy.py",
  "max_rounds": 2,
  "enable_fix": true
}
```

### 查询审查状态
```
GET /api/review/{session_id}/status
```

### 获取审查结果
```
GET /api/review/{session_id}/results
```

### 下载报告
```
GET /api/review/{session_id}/report
```

### WebSocket 实时进度
```
WS /ws/review/{session_id}
```

## 功能特性

### 1. 直观的界面设计
- 渐变色主题，现代化 UI
- 响应式布局，支持移动端
- 使用 TailwindCSS + Alpine.js 构建

### 2. 实时进度跟踪
- 进度条显示审查进度
- 实时更新发现的问题数量
- WebSocket 推送状态变化

### 3. 智能筛选与分类
- 按类别筛选（安全/Bug/性能/风格）
- 按严重度筛选（Critical/High/Medium/Low）
- 仅显示已确认的问题
- 统计卡片展示各类别问题数量

### 4. 详细的问题展示
- 问题标题、描述、位置
- 严重度标签和确认状态
- 修复建议展示
- 悬停效果和视觉反馈

### 5. 报告下载
- 一键下载 Markdown 格式报告
- 包含完整的审查结果

## 技术架构

### 后端
- **FastAPI**: 现代化异步 Web 框架
- **Uvicorn**: ASGI 服务器
- **WebSocket**: 实时双向通信
- **异步任务**: 后台执行审查工作流

### 前端
- **HTML5 + CSS3**: 标准 Web 技术
- **TailwindCSS**: 实用优先的 CSS 框架
- **Alpine.js**: 轻量级响应式框架
- **Font Awesome**: 图标库

## 配置要求

确保 `.env` 文件已正确配置：

```bash
# LLM Provider 配置
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxxx

# 或使用其他 Provider
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-xxxx

# 审查配置
MAX_REVIEW_ROUNDS=2
ENABLE_AUTO_FIX=true
SEVERITY_THRESHOLD=medium
```

## 开发说明

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行开发服务器
```bash
python -m src.main web --reload
```

### 测试 API
```bash
# 使用 curl
curl http://localhost:8000/api/config

# 或访问交互式文档
open http://localhost:8000/docs
```

## 生产部署

### 使用 Docker
```bash
docker build -t codesentinel-web .
docker run -p 8000:8000 --env-file .env codesentinel-web
```

### 使用 docker-compose
```bash
docker-compose up --build
```

### 环境变量
生产环境建议设置：
- `WORKERS=4` - Worker 进程数
- `LOG_LEVEL=info` - 日志级别
- `LANGSMITH_TRACING=true` - 可选的 LangSmith 追踪

## 注意事项

1. **安全性**: 生产环境应配置 CORS、认证和 HTTPS
2. **会话存储**: 当前使用内存存储，生产环境建议使用 Redis
3. **文件上传**: 当前仅支持路径输入，后续可添加文件上传功能
4. **并发限制**: 建议配置审查任务队列避免资源耗尽
