"""多轮对话与短期记忆：把历史消息一起发给模型。"""

from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-flash"
MAX_TURNS = 4


def create_system_message() -> dict[str, str]:
    """创建 system prompt。"""
    return {
        "role": "system",
        "content": (
            "你是一个面向初学者的 Python 和 agent 助手。"
            "请使用简洁、友好、清晰的中文回答。"
            "如果用户的问题依赖上文，请结合对话历史继续回答。"
        ),
    }


def trim_messages(messages: list[dict[str, str]], max_turns: int) -> list[dict[str, str]]:
    """只保留 system prompt 和最近 max_turns 轮对话。"""
    if not messages:
        return messages

    system_message = messages[0]
    recent_messages = messages[1:]
    max_message_count = max_turns * 2

    if len(recent_messages) > max_message_count:
        recent_messages = recent_messages[-max_message_count:]

    return [system_message, *recent_messages]


def call_llm(api_key: str, messages: list[dict[str, str]]) -> str:
    """调用 DeepSeek Chat API，返回模型回复的正文。"""
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
            "max_tokens": 300,
            "temperature": 0.7,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def main() -> None:
    """程序入口。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，请在仓库根目录的 .env 中填写")

    messages: list[dict[str, str]] = [create_system_message()]

    print("Memory Demo 已启动。输入 exit 或 quit 结束。")
    print(f"当前会保留最近 {MAX_TURNS} 轮对话作为短期记忆。")

    while True:
        user_input = input("\n你：").strip()

        if not user_input:
            print("请输入内容。")
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("对话结束。")
            break

        messages.append({"role": "user", "content": user_input})
        messages = trim_messages(messages, MAX_TURNS)

        try:
            answer = call_llm(api_key=api_key, messages=messages)
        except requests.RequestException as exc:
            print(f"\n请求失败：{exc}")
            if messages[-1]["role"] == "user":
                messages.pop()
            continue

        print(f"\n助手：{answer}")

        messages.append({"role": "assistant", "content": answer})
        messages = trim_messages(messages, MAX_TURNS)


if __name__ == "__main__":
    main()
