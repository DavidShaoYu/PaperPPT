"""大模型API客户端 - 支持DeepSeek/Qwen，兼容OpenAI SDK"""
import os
import json
from typing import Optional


class LLMClient:
    """统一的大模型调用接口"""

    def __init__(self, provider: str = "custom", model: Optional[str] = None):
        from config import LLM_CONFIG
        self.provider = provider

        if provider == "custom":
            self.base_url = LLM_CONFIG["base_url"]
            self.model = model or LLM_CONFIG["model"]
            self.api_key = os.environ.get(LLM_CONFIG["api_key_env"], "sk-placeholder")
        elif provider == "deepseek":
            self.base_url = "https://api.deepseek.com"
            self.model = model or "deepseek-chat"
            self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        elif provider == "qwen":
            self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            self.model = model or "qwen-plus"
            self.api_key = os.environ.get("QWEN_API_KEY", "")
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def chat(self, messages: list, temperature: float = 0.3,
             max_tokens: int = 2000) -> str:
        """普通对话"""
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def chat_with_tools(self, messages: list, tools: list,
                        temperature: float = 0.3) -> dict:
        """带Function Calling的对话"""
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
            max_tokens=2000,
        )

        message = response.choices[0].message
        result = {
            "content": message.content,
            "tool_calls": [],
        }

        if message.tool_calls:
            for tc in message.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        return result


class MockLLMClient:
    """模拟LLM客户端（无需API Key即可演示）"""

    def __init__(self):
        self.call_count = 0

    def chat(self, messages: list, **kwargs) -> str:
        self.call_count += 1
        return "基于当前态势分析，建议执行主动防御策略。"

    def chat_with_tools(self, messages: list, tools: list, **kwargs) -> dict:
        self.call_count += 1
        state_info = ""
        for msg in messages:
            if isinstance(msg.get("content"), str) and "port" in msg["content"]:
                state_info = msg["content"]
                break

        tool_calls = []
        if "封航前" in state_info or "warning" in state_info.lower():
            tool_calls = [{
                "id": f"call_{self.call_count}",
                "name": "optimize_split_route",
                "arguments": {"mode": "pre_closure_defense"},
            }]
        elif "封航中" in state_info or "closed" in state_info.lower():
            tool_calls = [{
                "id": f"call_{self.call_count}",
                "name": "optimize_split_route",
                "arguments": {"mode": "supply_assurance"},
            }]

        return {
            "content": "执行调度优化方案",
            "tool_calls": tool_calls,
        }
