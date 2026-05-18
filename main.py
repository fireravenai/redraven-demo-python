"""Minimal demo for the redraven Python SDK.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import redraven
from dotenv import load_dotenv
from openai import AsyncOpenAI

from util import (
    ask,
    ask_yes_no,
    coerce_test_id,
    default_test_name,
    demo_generate_run_with_progress,
    demo_run_existing_test_with_progress,
    select_case_count_preset,
    select_mode,
)

load_dotenv()

# Test generation defaults — edit these for your scenario.
# Certifications must be chosen from: GDPR, HIPAA, SOC2, ISO_42001, NIST_AI_RMF, TGV, PCI_DSS
DEFAULT_BUSINESS_CONTEXT = (
    "A medtech AI startup company handling sensitive customer data, helping hospitals "
    "and clinics to improve patient care and operational efficiency by helping doctors "
    "manage patients, get recommendations on what to ask the patients, and analyze "
    "medical records."
)
DEFAULT_USE_CASE = (
    "An AI agent helping doctors manage patients, get recommendations on what to ask "
    "the patients, and analyze medical records. Customer data protection and privacy "
    "compliance is very important. it should also not give medical advice"
)
DEFAULT_CERTIFICATIONS = [
    "HIPAA",
    # "GDPR",
    # "SOC2",
    # "ISO_42001",
    # "NIST_AI_RMF",
    # "TGV",
    # "PCI_DSS",
]
DEFAULT_SPECIFIC_POLICIES: list[str] = []
DEFAULT_MAX_POLICIES = 5
DEFAULT_MAX_PROMPTS_PER_POLICY = 2
_openai = AsyncOpenAI()


def build_test_metadata(
    *,
    use_images: bool,
    max_policies: int = DEFAULT_MAX_POLICIES,
    max_prompts_per_policy: int = DEFAULT_MAX_PROMPTS_PER_POLICY,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "business_context": DEFAULT_BUSINESS_CONTEXT,
        "use_case": DEFAULT_USE_CASE,
        "certifications": list(DEFAULT_CERTIFICATIONS),
        "max_policies": max_policies,
        "max_prompts_per_policy": max_prompts_per_policy,
        "modes": {
            "text": True,
            "image": use_images,
            "audio": False,
            "video": False,
        },
    }
    if DEFAULT_SPECIFIC_POLICIES:
        metadata["policies"] = list(DEFAULT_SPECIFIC_POLICIES)
    return metadata


def build_generate_kwargs(
    *,
    project_id: str,
    test_name: str,
    use_images: bool,
    max_policies: int = DEFAULT_MAX_POLICIES,
    max_prompts_per_policy: int = DEFAULT_MAX_PROMPTS_PER_POLICY,
) -> dict[str, Any]:
    generate_kwargs: dict[str, Any] = {
        "project_id": project_id,
        "test_name": test_name or default_test_name(),
        "business_context": DEFAULT_BUSINESS_CONTEXT,
        "use_case": DEFAULT_USE_CASE,
        "certifications": list(DEFAULT_CERTIFICATIONS),
        "max_policies": max_policies,
        "max_prompts_per_policy": max_prompts_per_policy,
        "metadata": build_test_metadata(
            use_images=use_images,
            max_policies=max_policies,
            max_prompts_per_policy=max_prompts_per_policy,
        ),
    }
    if DEFAULT_SPECIFIC_POLICIES:
        generate_kwargs["policies"] = [
            {"policy": policy} for policy in DEFAULT_SPECIFIC_POLICIES
        ]
    return generate_kwargs


async def echo_llm(
    prompt: str,
    messages: list[dict] | None = None,
) -> str:
    """Return the test case prompt unchanged (no external LLM) — for throughput testing."""
    if prompt.strip():
        return prompt
    if messages:
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return prompt or ""


async def call_llm(
    prompt: str,
    messages: list[dict] | None = None,
) -> str:
    """
    To modify to call your own LLM or agent. The default implementation calls OpenAI's gpt-4o chat model.
    """
    payload_messages = messages or [{"role": "user", "content": prompt}]
    resp = await _openai.chat.completions.create(
        model="gpt-4o",
        messages=payload_messages,
    )
    return resp.choices[0].message.content or ""


def select_llm(*, echo_only: bool):
    if echo_only:
        print("LLM: echo mode (returning each test case message as the response).")
        return echo_llm
    return call_llm


def print_result_summary(result: Any) -> None:
    print(f"state             = {result.state}")
    print(f"expected_cases    = {result.expected_cases}")
    print(f"received          = {result.received}")
    print(f"failed            = {result.failed}")
    print(f"failed_case_ids   = {result.failed_case_ids}")
    if result.summary:
        agg = result.summary.get("aggregated_policies") or []
        print(f"aggregated policies: {len(agg)}")


async def main() -> int:
    env_test_id = coerce_test_id(os.getenv("REDRAVEN_TEST_ID", ""))
    env_project_id = os.getenv("REDRAVEN_PROJECT_ID", "").strip()
    mode = select_mode()
    concurrency_raw = ask("Concurrency", default="20")
    try:
        concurrency = int(concurrency_raw)
    except ValueError:
        print("ERROR: concurrency must be an integer.", file=sys.stderr)
        return 2

    async with redraven.Client() as client:
        if mode == "generate_run":
            llm = select_llm(
                echo_only=ask_yes_no(
                    "Echo test case messages only (skip LLM API — speed test)",
                    default=False,
                ),
            )
            project_id = ask("Project ID for generation", default=env_project_id)
            if not project_id:
                print("ERROR: project_id is required to generate a test.", file=sys.stderr)
                return 2

            case_preset = select_case_count_preset()
            test_name = ask("Test name", default=default_test_name())
            use_images = ask_yes_no(
                "Enable image mode (image payloads for half of the cases)",
                default=False,
            )
            gen_kw = build_generate_kwargs(
                project_id=project_id,
                test_name=test_name,
                use_images=use_images,
                max_policies=case_preset["max_policies"],
                max_prompts_per_policy=case_preset["max_prompts_per_policy"],
            )

            result = await demo_generate_run_with_progress(
                client,
                generate_kwargs=gen_kw,
                llm=llm,
                concurrency=concurrency,
                retries=2,
                allow_partial=True,
            )
            print_result_summary(result)
            return 0

        if mode == "generate_only":
            project_id = ask("Project ID for generation", default=env_project_id)
            if not project_id:
                print("ERROR: project_id is required to generate a test.", file=sys.stderr)
                return 2

            case_preset = select_case_count_preset()
            test_name = ask("Test name", default=default_test_name())
            use_images = ask_yes_no(
                "Enable image mode (image payloads for half of the cases)",
                default=False,
            )
            gen_kw = build_generate_kwargs(
                project_id=project_id,
                test_name=test_name,
                use_images=use_images,
                max_policies=case_preset["max_policies"],
                max_prompts_per_policy=case_preset["max_prompts_per_policy"],
            )

            test_id = await client.generate_test(
                generate_kwargs=gen_kw,
            )
            print(f"generated test_id = {test_id}")
            return 0

        test_id = coerce_test_id(ask("Test ID to run", default=env_test_id))
        if not test_id:
            print("ERROR: test_id is required to run an existing test.", file=sys.stderr)
            return 2

        echo_default = os.getenv("REDRAVEN_ECHO", "").strip().lower() in ("1", "true", "yes")
        llm = select_llm(
            echo_only=ask_yes_no(
                "Echo test case messages only (skip LLM API — speed test)",
                default=echo_default,
            ),
        )
        result = await demo_run_existing_test_with_progress(
            client,
            test_id=test_id,
            llm=llm,
            concurrency=concurrency,
            retries=2,
            allow_partial=True,
        )

        print_result_summary(result)
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
