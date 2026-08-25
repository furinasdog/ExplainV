"""
ExplainV FastAPI 服务。

每台机器同时只处理一个视频生成任务。水平扩展由外部编排器
（UI 后端 + 阿里云 API）管理机器实例数量来实现。

启动::

    uvicorn src.api.app:app --host 0.0.0.0 --port 8000

接口：
    - ``POST /tasks``          提交视频生成任务（后台执行，返回 202）
    - ``GET  /status``          查询当前任务进度 / 结果
    - ``GET  /health``          健康检查 + 忙碌状态
    - ``GET  /files/{filename}`` 下载生成的视频
"""

import asyncio
import base64
import sys
import threading
import traceback
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.api.config import settings
from src.api.schemas import (
    HealthResponse,
    StatusResponse,
    TaskAcceptedResponse,
    TaskRequest,
    TaskResult,
)

# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(_PROJECT_ROOT / ".env")

Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="ExplainV API",
    description="AI 题解视频生成服务（单实例单任务）",
    version="1.2.0",
)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 全局状态（进程内共享，线程安全通过 lock）
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_task_lock = asyncio.Lock()

_state = {
    "busy": False,
    "stage": None,
    "progress": None,
    "result": None,       # TaskResult dict or None
    "error": None,        # str or None
}


def _reset_state():
    with _lock:
        _state["busy"] = False
        _state["stage"] = None
        _state["progress"] = None
        _state["result"] = None
        _state["error"] = None


def _set_progress(stage: str, progress: float):
    with _lock:
        _state["stage"] = stage
        _state["progress"] = progress


def _set_result(result: dict):
    with _lock:
        _state["result"] = result
        _state["busy"] = False


def _set_error(error: str):
    with _lock:
        _state["error"] = error
        _state["busy"] = False


def _get_state() -> dict:
    with _lock:
        return dict(_state)


# ---------------------------------------------------------------------------
# Pipeline 执行（在线程池中运行）
# ---------------------------------------------------------------------------

def _run_pipeline_sync(request: TaskRequest) -> dict:
    """同步执行 Pipeline，返回结果 dict。在 asyncio.to_thread 中调用。"""
    from src.core.pipeline import Pipeline
    from src.options import ExplanationOptions
    from utils.logger import get_logger, setup_logging

    setup_logging()
    logger = get_logger("api.task")

    options = ExplanationOptions.from_selection(
        request.sections, brief=request.brief_solution
    )

    # 处理图片（如有）
    image_path = None
    if request.problem_image_base64:
        image_data = base64.b64decode(request.problem_image_base64)
        image_path = str(
            Path(settings.data_dir) / f"_api_tmp_{uuid.uuid4().hex[:8]}.png"
        )
        Path(image_path).parent.mkdir(parents=True, exist_ok=True)
        Path(image_path).write_bytes(image_data)

    ref_audio = request.ref_audio_path or settings.default_ref_audio

    def on_progress(stage: str, value: float):
        _set_progress(stage, value)
        logger.info("[%s] %.0f%%", stage, value * 100)

    pipeline = Pipeline(
        ref_audio_path=ref_audio,
        quality=request.quality,
        data_dir=settings.data_dir,
        on_progress=on_progress,
        options=options,
    )

    try:
        if image_path:
            result = pipeline.run_image(image_path)
        else:
            result = pipeline.run_text(request.problem_text or "")

        video_name = Path(result.video_path).name
        return {
            "video_url": f"/files/{video_name}",
            "explanation": result.explanation,
            "code": result.scene.code,
        }

    finally:
        if image_path and Path(image_path).exists():
            try:
                Path(image_path).unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@app.post("/tasks", response_model=TaskAcceptedResponse, status_code=202)
async def create_task(request: TaskRequest):
    """提交视频生成任务。

    机器忙时返回 503。空闲时立即返回 202，任务在后台执行，
    客户端通过轮询 ``GET /status`` 获取进度和结果。
    """
    if not request.problem_text and not request.problem_image_base64:
        raise HTTPException(
            status_code=400,
            detail="必须提供 problem_text 或 problem_image_base64",
        )

    s = _get_state()
    if s["busy"]:
        raise HTTPException(
            status_code=503,
            detail="当前机器正在处理任务，请稍后重试或请求其他实例",
        )

    # 重置状态并开始后台任务
    _reset_state()
    with _lock:
        _state["busy"] = True
        _state["stage"] = "initializing"
        _state["progress"] = 0.0

    async def _background_run():
        async with _task_lock:
            try:
                result = await asyncio.to_thread(_run_pipeline_sync, request)
                _set_result(result)
            except Exception as exc:
                _set_error(f"{exc}\n\n{traceback.format_exc()}")

    asyncio.create_task(_background_run())

    return TaskAcceptedResponse(
        status="running",
        message="任务已接受，请轮询 /status 查看进度",
    )


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """查询当前任务的进度和结果。"""
    s = _get_state()

    result = None
    if s["result"] is not None:
        result = TaskResult(**s["result"])

    return StatusResponse(
        busy=s["busy"],
        stage=s["stage"],
        progress=s["progress"],
        result=result,
        error=s["error"],
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查，供 k8s liveness/readiness probe 使用。"""
    s = _get_state()
    return HealthResponse(status="ok", busy=s["busy"])


@app.get("/files/{filename}")
async def download_file(filename: str):
    """下载生成的视频文件。"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    file_path = Path(settings.data_dir) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="video/mp4",
    )
