"""测试 Web API 端点。"""
import pytest
from fastapi.testclient import TestClient

from src.web.app import app


client = TestClient(app)


def test_index():
    """测试主页。"""
    response = client.get("/")
    assert response.status_code == 200
    assert "CodeSentinel" in response.text


def test_get_config():
    """测试获取配置。"""
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "llm_provider" in data
    assert "max_review_rounds" in data


def test_start_review_invalid_path():
    """测试无效路径审查。"""
    response = client.post(
        "/api/review",
        json={
            "path": "/nonexistent/path",
            "max_rounds": 2,
            "enable_fix": True,
        },
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_get_status_invalid_session():
    """测试查询不存在的会话。"""
    response = client.get("/api/review/invalid_session/status")
    assert response.status_code == 404


def test_get_results_invalid_session():
    """测试获取不存在会话的结果。"""
    response = client.get("/api/review/invalid_session/results")
    assert response.status_code == 404
