"""CodeSentinel Web 服务器。

使用 FastAPI 提供 Web 界面和 RESTful API。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agent import initial_state
from src.config import get_settings
from src.graph import build_graph
from src.observability import configure_logging, get_logger


app = FastAPI(
    title="CodeSentinel",
    description="智能代码审查与 Bug 修复 Agent",
    version="0.1.0",
)

# 静态文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

configure_logging()
log = get_logger("web")


class ReviewRequest(BaseModel):
    """审查请求参数。"""
    path: str
    max_rounds: int = 0
    enable_fix: bool = True


class ReviewStatus(BaseModel):
    """审查状态。"""
    status: str  # pending, running, completed, error
    message: str = ""
    progress: int = 0  # 0-100
    findings_count: int = 0
    confirmed_count: int = 0


# 全局状态存储（生产环境应使用 Redis）
review_sessions: dict[str, dict[str, Any]] = {}


@app.get("/", response_class=HTMLResponse)
async def index():
    """主页。"""
    html_path = static_dir / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return """
    <!DOCTYPE html>
    <html>
    <head><title>CodeSentinel</title></head>
    <body>
        <h1>CodeSentinel Web UI</h1>
        <p>静态文件未找到。请确保 static/index.html 存在。</p>
    </body>
    </html>
    """


@app.get("/api/config")
async def get_config():
    """获取当前配置。"""
    s = get_settings()
    return {
        "llm_provider": s.llm_provider,
        "is_configured": s.is_provider_configured,
        "max_review_rounds": s.max_review_rounds,
        "enable_auto_fix": s.enable_auto_fix,
        "severity_threshold": s.severity_threshold,
    }


@app.post("/api/review")
async def start_review(request: ReviewRequest):
    """启动代码审查任务。"""
    target_path = Path(request.path)

    if not target_path.exists():
        return JSONResponse(
            status_code=400,
            content={"error": f"路径不存在: {request.path}"}
        )

    s = get_settings()
    rounds = request.max_rounds or s.max_review_rounds
    enable_fix = request.enable_fix and s.enable_auto_fix

    # 生成会话 ID
    import uuid
    session_id = str(uuid.uuid4())[:8]

    # 初始化会话状态
    review_sessions[session_id] = {
        "status": "pending",
        "path": str(target_path),
        "progress": 0,
        "findings": [],
        "report": "",
    }

    # 异步执行审查
    asyncio.create_task(run_review(session_id, target_path, rounds, enable_fix))

    return {"session_id": session_id, "status": "pending"}


async def run_review(session_id: str, path: Path, max_rounds: int, enable_fix: bool):
    """后台执行审查任务。"""
    import traceback

    try:
        review_sessions[session_id]["status"] = "running"
        review_sessions[session_id]["progress"] = 10

        log.info("web_review_start", session_id=session_id, path=str(path))

        # 检查路径是否可访问
        if not path.exists():
            raise ValueError(f"路径不存在: {path}")

        review_sessions[session_id]["progress"] = 20
        log.info("web_review_init_state", session_id=session_id)

        state = initial_state(path, max_rounds=max_rounds, enable_fix=enable_fix)

        review_sessions[session_id]["progress"] = 30
        log.info("web_review_build_graph", session_id=session_id)

        graph = build_graph()

        review_sessions[session_id]["progress"] = 40
        log.info("web_review_invoke_start", session_id=session_id)

        # 执行审查（同步调用，在异步任务中）
        final_state = await asyncio.to_thread(
            graph.invoke, state, {"recursion_limit": 30}
        )

        review_sessions[session_id]["progress"] = 90
        log.info("web_review_extract_results", session_id=session_id)

        # 提取结果
        findings = final_state.get("findings", [])
        confirmed = [f for f in findings if f.confirmed]
        report_md = final_state.get("report_md", "")

        review_sessions[session_id].update({
            "status": "completed",
            "progress": 100,
            "findings": [
                {
                    "file": f.file,
                    "line": f.line,
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "description": f.detail,
                    "confirmed": f.confirmed,
                    "suggestion": f.suggestion or "",
                }
                for f in findings
            ],
            "confirmed_count": len(confirmed),
            "report": report_md,
        })

        log.info("web_review_done", session_id=session_id, findings=len(findings))

    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()

        log.error(
            "web_review_error",
            session_id=session_id,
            error=error_msg,
            traceback=error_trace
        )

        review_sessions[session_id].update({
            "status": "error",
            "progress": 0,
            "error": error_msg,
            "error_detail": error_trace,
        })


@app.get("/api/review/{session_id}/status")
async def get_review_status(session_id: str):
    """获取审查任务状态。"""
    if session_id not in review_sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})

    session = review_sessions[session_id]
    response = {
        "status": session["status"],
        "progress": session["progress"],
        "findings_count": len(session.get("findings", [])),
        "confirmed_count": session.get("confirmed_count", 0),
    }

    # 如果有错误，返回错误信息
    if session["status"] == "error":
        response["error"] = session.get("error", "未知错误")
        response["error_detail"] = session.get("error_detail", "")

    return response


@app.get("/api/review/{session_id}/results")
async def get_review_results(session_id: str):
    """获取审查结果。"""
    if session_id not in review_sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})

    session = review_sessions[session_id]
    if session["status"] != "completed":
        return JSONResponse(status_code=400, content={"error": "审查未完成"})

    return {
        "findings": session["findings"],
        "report": session["report"],
        "path": session["path"],
    }


@app.get("/api/review/{session_id}/report")
async def download_report(session_id: str):
    """下载报告文件。"""
    if session_id not in review_sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})

    session = review_sessions[session_id]
    if session["status"] != "completed":
        return JSONResponse(status_code=400, content={"error": "审查未完成"})

    import tempfile
    # 临时写入报告文件
    tmp_dir = Path(tempfile.gettempdir())
    report_path = tmp_dir / f"codesentinel_{session_id}.md"
    report_path.write_text(session["report"], encoding="utf-8")

    return FileResponse(
        path=str(report_path),
        filename=f"codesentinel_report_{session_id}.md",
        media_type="text/markdown",
    )


@app.websocket("/ws/review/{session_id}")
async def websocket_review(websocket: WebSocket, session_id: str):
    """WebSocket 实时推送审查进度。"""
    await websocket.accept()

    try:
        while True:
            if session_id not in review_sessions:
                await websocket.send_json({"error": "会话不存在"})
                break

            session = review_sessions[session_id]
            await websocket.send_json({
                "status": session["status"],
                "progress": session["progress"],
                "findings_count": len(session.get("findings", [])),
            })

            if session["status"] in ["completed", "error"]:
                break

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        log.info("websocket_disconnect", session_id=session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
