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

    def call_model_with_image(self,
                              text: str,
                              img_path: str,
                              system_prompt: Optional[str] = None) -> None | Any:
        """调用API接口（带图片）"""
        messages = self.build_messages_with_image(text, img_path, system_prompt)
        logger.info("Calling LLM with image (model=%s)", self.model_name)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            extra_body={"enable_thinking": True},
            timeout=2400
        )
        result = self._process_response(response)
        logger.info("LLM response: %s type, %d chars",
                     type(result).__name__, len(result) if result else 0)
        return result

    def call_model_without_image(self,
                                 text: str,
                                 system_prompt: Optional[str] = None) -> None | Any:
        """调用API接口（无图片）"""
        messages = self.build_messages_without_image(text, system_prompt)
        logger.info("Calling LLM text-only (model=%s)", self.model_name)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            extra_body={"enable_thinking": True},
            timeout=2400
        )
        result = self._process_response(response)
        logger.info("LLM response: %s type, %d chars",
                     type(result).__name__, len(result) if result else 0)
        return result

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

    def _process_response(self, response: Any) -> None | Any:
        """处理API返回结果"""
        # Some API providers return a plain string instead of
        # an OpenAI ChatCompletion object — handle both cases.
        if isinstance(response, str):
            # Detect HTML responses (API gateway returning a web page)
            stripped = response.lstrip()
            if stripped.startswith("<!") or stripped.startswith("<html"):
                logger.error("API returned HTML instead of JSON:\n%s", response[:300])
                raise RuntimeError(
                    "API 返回了 HTML 页面而非 JSON 响应。"
                    "请检查 EXPLAINV_API_URL 是否正确指向 API 端点。"
                )
            return response

        if not response or not hasattr(response, "choices") or not response.choices:
            return None

        choice = response.choices[0]
        message = choice.message

        content = message.content or None

        return content