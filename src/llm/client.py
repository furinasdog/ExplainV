import os
import base64
from typing import List, Dict, Any, Optional
import openai

from utils.logger import get_logger

logger = get_logger(__name__)


class Client:
    def __init__(self, system_prompt: str):
        self.api_key = os.getenv("EXPLAINV_API_KEY", None)
        self.base_url = os.getenv("EXPLAINV_API_URL", None)
        self.model_name = os.getenv("EXPLAINV_USE_MODEL", "Kimi-k3")
        if self.api_key is None or self.base_url is None:
            raise RuntimeError("API or key missing")

        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.system_prompt = system_prompt

    # Default per-request timeout in seconds (long generations are expected)
    REQUEST_TIMEOUT = 2400

    def call_model_with_image(self,
                              text: str,
                              img_path: str,
                              system_prompt: Optional[str] = None) -> None | Any:
        """调用API接口（带图片，流式接收）"""
        messages = self.build_messages_with_image(text, img_path, system_prompt)
        logger.info("Calling LLM with image (model=%s)", self.model_name)
        return self._streaming_call(messages)

    def call_model_without_image(self,
                                 text: str,
                                 system_prompt: Optional[str] = None) -> None | Any:
        """调用API接口（无图片，流式接收）"""
        messages = self.build_messages_without_image(text, system_prompt)
        logger.info("Calling LLM text-only (model=%s)", self.model_name)
        return self._streaming_call(messages)

    def build_messages_with_image(self,
                                  text: str,
                                  img_path: str,
                                  system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        """构建提示词（带图片）"""
        sys_prompt = system_prompt if system_prompt is not None else self.system_prompt

        with open(img_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        messages = [
            {
                "role": "system",
                "content": sys_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
        return messages

    def build_messages_without_image(self,
                                     text: str,
                                     system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        """构建提示词（无图片）"""
        sys_prompt = system_prompt if system_prompt is not None else self.system_prompt

        messages = [
            {
                "role": "system",
                "content": sys_prompt
            },
            {
                "role": "user",
                "content": text
            }
        ]
        return messages

    def _streaming_call(self, messages: List[Dict[str, Any]]) -> None | str:
        """发起流式请求并拼接完整回复。

        使用 stream=True 让 token 边生成边回传，连接上始终有数据流动，
        从而绕过反向代理的空闲超时（非流式长请求会被网关以 504 掐断）。

        注意：思考类模型会在 delta 中下发 reasoning_content，
        这里只累积 content 字段。
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
            extra_body={"enable_thinking": True},
            timeout=self.REQUEST_TIMEOUT,
        )

        parts: List[str] = []
        for chunk in response:
            # 尾部可能存在仅携带 usage、无 choices 的分块
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None) if delta is not None else None
            if content:
                parts.append(content)

        result = "".join(parts)

        # Detect HTML responses (API gateway returning a web page)
        stripped = result.lstrip()
        if stripped.startswith("<!") or stripped.startswith("<html"):
            logger.error("API returned HTML instead of JSON:\n%s", result[:300])
            raise RuntimeError(
                "API 返回了 HTML 页面而非 JSON 响应。"
                "请检查 EXPLAINV_API_URL 是否正确指向 API 端点。"
            )

        logger.info("LLM response: str type, %d chars",
                     len(result) if result else 0)
        return result or None