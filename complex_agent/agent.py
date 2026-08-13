"""Company1 complex agent: OpenAI chat + tool loop."""
from __future__ import annotations

import json
from typing import Any

from complex_agent.prompts import CURRENT_USER_WRAPPER, SYSTEM_PROMPT
from complex_agent.tools import TOOL_DEFINITIONS, dispatch_tool

DEFAULT_MODEL = "gpt-4o"
MAX_TOOL_ROUNDS = 8


def _extract_user_text(prompt: str, messages: list[dict] | None) -> str:
    if prompt and prompt.strip():
        return prompt.strip()
    if messages:
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts = [
                    str(p.get("text", ""))
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                joined = "\n".join(p for p in parts if p.strip())
                if joined.strip():
                    return joined.strip()
    return prompt or ""


def _build_messages(prompt: str, messages: list[dict] | None) -> list[dict[str, Any]]:
    user_text = _extract_user_text(prompt, messages)
    wrapped = CURRENT_USER_WRAPPER.format(user_message=user_text)

    out: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Keep prior turns if provided (e.g. attack multi-turn), but always
    # ensure the latest user content is wrapped with the Bob session hint.
    if messages:
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role not in ("user", "assistant", "system", "tool"):
                continue
            if role == "system":
                # Agent system prompt is authoritative; skip external system.
                continue
            if role == "user" and content == user_text:
                continue
            out.append({"role": role, "content": content})

    out.append({"role": "user", "content": wrapped})
    return out


async def run_complex_agent(
    prompt: str,
    messages: list[dict] | None = None,
    *,
    model: str = DEFAULT_MODEL,
) -> str:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI is not installed. Run: uv sync --extra openai"
        ) from exc

    client = AsyncOpenAI()
    chat_messages = _build_messages(prompt, messages)

    for _ in range(MAX_TOOL_ROUNDS):
        resp = await client.chat.completions.create(
            model=model,
            messages=chat_messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )
        choice = resp.choices[0].message
        tool_calls = choice.tool_calls or []

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": choice.content or "",
        }
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in tool_calls
            ]
        chat_messages.append(assistant_msg)

        if not tool_calls:
            return (choice.content or "").strip()

        for tc in tool_calls:
            raw_args = tc.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
                if not isinstance(args, dict):
                    args = {}
            except json.JSONDecodeError:
                args = {}
            result = dispatch_tool(tc.function.name, args)
            chat_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    return (
        "I reached the tool-call limit for this turn. Please rephrase your "
        "request or ask one question at a time."
    )
