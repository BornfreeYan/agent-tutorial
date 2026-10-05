"""DeepSeek Hello World：一次最小的模型调用。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-flash"


def build_messages() -> list[dict[str, str]]:
    """构造一次对话的消息列表。"""
    return [
        {
            "role": "system",
            "content": (
                "你是一个面向初学者的 Python 和 agent 助手。"
                "回答时尽量简洁、友好，并在必要时给出清晰步骤。"
            ),
        },
        {
            "role": "user",
            "content": "请用一句话介绍什么是 Agent，并给一个生活中的类比。",
        },
    ]


def call_llm(api_key: str, messages: list[dict[str, str]]) -> dict:
    """请求 DeepSeek Chat Completions 接口，返回原始响应 JSON。"""
    response = requests.post(
        API_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "stream": False,
            "thinking": {"type": "disabled"},
            "max_tokens": 200,
            "temperature": 0.7,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    """程序入口。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，请在仓库根目录的 .env 中填写")

    messages = build_messages()

    print("=== 发送给模型的消息 ===")
    print(json.dumps(messages, ensure_ascii=False, indent=2))

    result = call_llm(api_key=api_key, messages=messages)

    print("\n=== 模型回复 ===")
    print(result["choices"][0]["message"]["content"])

    usage = result.get("usage")
    if usage:
        print("\n=== Token 用量 ===")
        print(json.dumps(usage, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
