"""最小工具调用：让模型通过一次工具调用完成加法。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-flash"
MAX_TOOL_ROUNDS = 5

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "计算两个数字之和。用户要求做加法时必须使用这个工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "第一个加数"},
                    "b": {"type": "number", "description": "第二个加数"},
                },
                "required": ["a", "b"],
            },
        },
    }
]


def add(a: float, b: float) -> dict:
    """本地真正执行加法的函数。"""
    return {"ok": True, "result": a + b}


def call_llm(api_key: str, messages: list[dict]) -> dict:
    """请求 DeepSeek Chat API，返回 assistant message。"""
    response = requests.post(
        API_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "stream": False,
            "thinking": {"type": "disabled"},
            "temperature": 0,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]


def execute_tool_call(tool_call: dict) -> dict:
    """把模型请求的工具调用，路由到本地函数。"""
    name = tool_call["function"]["name"]
    raw_arguments = tool_call["function"]["arguments"]

    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"参数不是合法 JSON：{exc}，请重新给出完整参数。"}

    if name == "add":
        return add(arguments["a"], arguments["b"])

    return {"ok": False, "error": f"未知工具：{name}"}


def run_agent_turn(api_key: str, question: str) -> str:
    """执行一次完整的工具调用闭环，返回最终答复。"""
    messages = [
        {
            "role": "system",
            "content": "你需要计算两个数之和时，必须调用 add 工具，不要自己心算。",
        },
        {"role": "user", "content": question},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        assistant_message = call_llm(api_key=api_key, messages=messages)
        tool_calls = assistant_message.get("tool_calls") or []

        if not tool_calls:
            return assistant_message.get("content") or "模型没有返回内容。"

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.get("content"),
                "tool_calls": tool_calls,
            }
        )

        for tool_call in tool_calls:
            print(f"[工具调用] {tool_call['function']['name']}")
            print(f"[工具参数] {tool_call['function']['arguments']}")

            tool_result = execute_tool_call(tool_call)
            print(f"[工具结果] {json.dumps(tool_result, ensure_ascii=False)}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

    return "工具调用轮数过多，已停止。"


def main() -> None:
    """程序入口。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，请在仓库根目录的 .env 中填写")

    question = input("你：").strip()
    if not question:
        raise SystemExit("没有输入内容。")

    print(f"\n助手：{run_agent_turn(api_key=api_key, question=question)}")


if __name__ == "__main__":
    main()
