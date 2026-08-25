"""
API 服务配置。

通过环境变量或 ``.env`` 文件加载：

- ``EXPLAINV_TASK_TIMEOUT``: 任务超时时间，秒（默认 7200）
- ``EXPLAINV_DATA_DIR``: 生成的视频和脚本存储目录（默认 ``./data``）
- ``EXPLAINV_CORS_ORIGINS``: 允许的跨域来源，逗号分隔（默认 ``*``）
- ``EXPLAINV_DEFAULT_QUALITY``: 默认渲染画质（默认 ``l``）
- ``EXPLAINV_DEFAULT_REF_AUDIO``: 默认参考音频路径
"""

from pathlib import Path

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """ExplainV API configuration."""

    task_timeout: int = 7200
    data_dir: str = str(_PROJECT_ROOT / "data")
    cors_origins: str = "*"
    default_quality: str = "l"
    default_ref_audio: str = str(_PROJECT_ROOT / "asset" / "mar7th.wav")

    # OSS (for uploading generated videos)
    oss_region: str = ""
    oss_bucket: str = ""
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""

    model_config = {"env_prefix": "EXPLAINV_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
