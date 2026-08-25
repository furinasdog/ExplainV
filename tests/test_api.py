"""Tests for the FastAPI service (src/api/)."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.api.schemas import (
    HealthResponse,
    StatusResponse,
    TaskAcceptedResponse,
    TaskRequest,
    TaskResult,
)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestTaskRequest:
    def test_defaults(self):
        req = TaskRequest(problem_text="求解 x+1=2")
        assert req.quality == "l"
        assert req.brief_solution is False
        assert req.sections is None
        assert req.problem_image_base64 is None

    def test_image_input(self):
        req = TaskRequest(problem_image_base64="aGVsbG8=")
        assert req.problem_image_base64 == "aGVsbG8="
        assert req.problem_text is None


class TestTaskAcceptedResponse:
    def test_defaults(self):
        resp = TaskAcceptedResponse()
        assert resp.status == "running"


class TestStatusResponse:
    def test_idle(self):
        resp = StatusResponse(busy=False)
        assert resp.stage is None
        assert resp.progress is None
        assert resp.result is None

    def test_running(self):
        resp = StatusResponse(busy=True, stage="rendering", progress=0.5)
        assert resp.stage == "rendering"

    def test_completed(self):
        resp = StatusResponse(
            busy=False,
            stage="done",
            progress=1.0,
            result=TaskResult(
                video_url="/files/abc.mp4",
                explanation="题解",
                code="class Scene...",
            ),
        )
        assert resp.result.video_url == "/files/abc.mp4"

    def test_failed(self):
        resp = StatusResponse(busy=False, error="LLM 超时")
        assert resp.error == "LLM 超时"


class TestHealthResponse:
    def test_idle(self):
        resp = HealthResponse(busy=False)
        assert resp.status == "ok"
        assert resp.busy is False

    def test_busy(self):
        resp = HealthResponse(busy=True)
        assert resp.busy is True


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestEndpoints:
    """Integration tests using FastAPI TestClient with mocked Pipeline."""

    @pytest.fixture(autouse=True)
    def _setup_client(self):
        from fastapi.testclient import TestClient

        from src.api.app import app, _reset_state

        _reset_state()
        self.client = TestClient(app)

    def test_health_idle(self):
        """GET /health when idle."""
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["busy"] is False

    def test_status_idle(self):
        """GET /status when idle."""
        resp = self.client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["busy"] is False
        assert data["stage"] is None

    def test_create_task_no_input(self):
        """POST /tasks without text or image should return 400."""
        resp = self.client.post("/tasks", json={})
        assert resp.status_code == 400

    @patch("src.api.app._run_pipeline_sync")
    def test_create_task_accepts_and_returns_202(self, mock_pipeline):
        """POST /tasks should return 202 and run pipeline in background."""
        mock_pipeline.return_value = {
            "video_url": "/files/test.mp4",
            "explanation": "题解",
            "code": "class Scene...",
        }

        resp = self.client.post(
            "/tasks",
            json={"problem_text": "求解 x+1=2"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "running"

    @patch("src.api.app._run_pipeline_sync")
    def test_status_shows_progress(self, mock_pipeline):
        """GET /status should show progress during execution."""
        # Make pipeline update progress state before returning
        def slow_pipeline(req):
            from src.api.app import _set_progress
            _set_progress("rendering", 0.5)
            return {
                "video_url": "/files/test.mp4",
                "explanation": "题解",
                "code": "class Scene...",
            }

        mock_pipeline.side_effect = slow_pipeline

        # Start task
        self.client.post("/tasks", json={"problem_text": "求解 x+1=2"})

        # Poll status (may catch it mid-execution or after completion)
        import time
        time.sleep(0.1)
        resp = self.client.get("/status")
        assert resp.status_code == 200

    @patch("src.api.app._run_pipeline_sync")
    def test_status_shows_result_after_completion(self, mock_pipeline):
        """GET /status should show result after pipeline completes."""
        mock_pipeline.return_value = {
            "video_url": "/files/done.mp4",
            "explanation": "完整题解",
            "code": "class DoneScene...",
        }

        self.client.post("/tasks", json={"problem_text": "1+1=?"})

        # Wait for background task to complete
        import time
        time.sleep(0.5)

        resp = self.client.get("/status")
        data = resp.json()
        assert data["busy"] is False
        assert data["result"] is not None
        assert data["result"]["video_url"] == "/files/done.mp4"

    @patch("src.api.app._run_pipeline_sync")
    def test_status_shows_error_on_failure(self, mock_pipeline):
        """GET /status should show error when pipeline fails."""
        mock_pipeline.side_effect = RuntimeError("LLM timeout")

        self.client.post("/tasks", json={"problem_text": "1+1=?"})

        import time
        time.sleep(0.5)

        resp = self.client.get("/status")
        data = resp.json()
        assert data["busy"] is False
        assert data["error"] is not None
        assert "LLM timeout" in data["error"]

    @patch("src.api.app._run_pipeline_sync")
    def test_busy_rejects_second_request(self, mock_pipeline):
        """POST /tasks while busy should return 503."""
        import threading

        barrier = threading.Event()

        def blocking_pipeline(req):
            barrier.wait(timeout=5)
            return {
                "video_url": "/files/test.mp4",
                "explanation": "题解",
                "code": "class Scene...",
            }

        mock_pipeline.side_effect = blocking_pipeline

        # Start first task
        resp1 = self.client.post("/tasks", json={"problem_text": "task 1"})
        assert resp1.status_code == 202

        # Wait a bit for the background task to start
        import time
        time.sleep(0.2)

        # Second task should be rejected
        resp2 = self.client.post("/tasks", json={"problem_text": "task 2"})
        assert resp2.status_code == 503

        # Unblock the first task
        barrier.set()
        time.sleep(0.5)

    def test_download_file_invalid_name(self):
        """GET /files with path traversal should be rejected."""
        resp = self.client.get("/files/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404)

    def test_download_file_not_found(self):
        """GET /files/nonexistent.mp4 should return 404."""
        resp = self.client.get("/files/nonexistent.mp4")
        assert resp.status_code == 404
