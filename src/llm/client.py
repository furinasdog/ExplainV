import os
import base64
from typing import List, Dict, Any, Optional
import openai

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
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            extra_body={"enable_thinking": True}
        )
        return self._process_response(response)

    def call_model_without_image(self,
                                 text: str,
                                 system_prompt: Optional[str] = None) -> None | Any:
        """调用API接口（无图片）"""
        messages = self.build_messages_without_image(text, system_prompt)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            extra_body={"enable_thinking": True}
        )
        return self._process_response(response)

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

    def _process_response(self, response: Any) ->  None | Any:
        """处理API返回结果"""
        if not response or not response.choices:
            return {
                "content": "",
                "reasoning_content": "",
                "finish_reason": None,
                "usage": None
            }

        choice = response.choices[0]
        message = choice.message

        content = message.content or None

        return content