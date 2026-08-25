"""
API 请求 / 响应 Pydantic 模型。
"""

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 请求
# ---------------------------------------------------------------------------

class TaskRequest(BaseModel):
    """提交视频生成任务的请求体。"""

    problem_text: Optional[str] = Field(
        default=None, description="题目文本（与 problem_image_base64 二选一）"
    )
    problem_image_base64: Optional[str] = Field(
        default=None, description="题目图片（Base64 编码，与 problem_text 二选一）"
    )
    ref_audio_path: Optional[str] = Field(
        default=None, description="参考音频路径（用于语音克隆，不传则使用默认）"
    )
    quality: str = Field(
        default="l",
        description="渲染画质: l(480p) / m(720p) / h(1080p) / k(4K)",
    )
    sections: Optional[list[str]] = Field(
        default=None,
        description="启用的讲解模块 key 列表，不传则使用全部模块",
    )
    brief_solution: bool = Field(
        default=False, description="是否启用简略解答模式"
    )
    task_id: Optional[str] = Field(
        default=None, description="外部任务 ID（由 WebUI 后端传入，用于进度关联）"
    )


# ---------------------------------------------------------------------------
# 响应
# ---------------------------------------------------------------------------

class TaskAcceptedResponse(BaseModel):
    """POST /tasks 返回 202 时的响应体。"""

    status: str = "running"
    message: str = "任务已接受，请轮询 /status 查看进度"


class TaskResult(BaseModel):
    """已完成任务的结果。"""

    video_url: str = Field(description="视频下载 URL")
    explanation: str = Field(description="LLM 生成的题解文本")
    code: str = Field(description="生成的 Manim 代码")


class StatusResponse(BaseModel):
    """GET /status 响应体。"""

    busy: bool = Field(description="当前是否有任务在执行")
    task_id: Optional[str] = Field(default=None, description="当前处理的外部任务 ID")
    stage: Optional[str] = Field(default=None, description="当前阶段名称")
    progress: Optional[float] = Field(default=None, description="进度 0.0–1.0")
    result: Optional[TaskResult] = Field(default=None, description="任务结果（仅完成时）")
    error: Optional[str] = Field(default=None, description="错误信息（仅失败时）")


class HealthResponse(BaseModel):
    """GET /health 响应体。"""

    status: str = "ok"
    busy: bool = Field(description="当前是否有任务在执行")
