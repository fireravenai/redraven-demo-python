"""Minimal demo for the redraven Python SDK.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import redraven
from dotenv import load_dotenv

from util import ask, ask_yes_no, coerce_test_id, select_mode

load_dotenv()

# Test generation defaults — edit these for your scenario.
# Certifications must be chosen from: GDPR, HIPAA, SOC2, ISO_42001, NIST_AI_RMF, TGV, PCI_DSS
DEFAULT_TEST_NAME = "Test_2026-05-09"
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
DEFAULT_MAX_POLICIES = 5
DEFAULT_MAX_PROMPTS_PER_POLICY = 2



from openai import OpenAI
_openai = OpenAI()

def call_llm(
    prompt: str,
    messages: list[dict] | None = None,
) -> str:
    """
    To modify to call your own LLM or agent. The default implementation calls OpenAI's gpt-4o chat model.
    """
    payload_messages = messages or [{"role": "user", "content": prompt}]
    resp = _openai.chat.completions.create(
        model="gpt-4o",
        messages=payload_messages,
    )
    return resp.choices[0].message.content or ""



async def main() -> int:
    env_test_id = coerce_test_id(os.getenv("REDRAVEN_TEST_ID", ""))
    env_project_id = os.getenv("REDRAVEN_PROJECT_ID", "").strip()
    mode = select_mode()
    concurrency_raw = ask("Concurrency", default="4")
    try:
        concurrency = int(concurrency_raw)
    except ValueError:
        print("ERROR: concurrency must be an integer.", file=sys.stderr)
        return 2

    async with redraven.Client() as client:
        if mode == "generate_run":
            project_id = ask("Project ID for generation", default=env_project_id)
            if not project_id:
                print("ERROR: project_id is required to generate a test.", file=sys.stderr)
                return 2

            test_name = ask("Test name", default=DEFAULT_TEST_NAME)
            use_images = ask_yes_no(
                "Enable image mode (image payloads for half of the cases)",
                default=False,
            )
            gen_kw: dict[str, Any] = {
                "project_id": project_id,
                "test_name": test_name or DEFAULT_TEST_NAME,
                "business_context": DEFAULT_BUSINESS_CONTEXT,
                "use_case": DEFAULT_USE_CASE,
                "certifications": DEFAULT_CERTIFICATIONS,
                "max_policies": DEFAULT_MAX_POLICIES,
                "max_prompts_per_policy": DEFAULT_MAX_PROMPTS_PER_POLICY,
            }
            if use_images:
                gen_kw["metadata"] = {"modes": {"image": True}}

            result = await client.generate_and_run_test(
                generate_kwargs=gen_kw,
                llm=call_llm,
                concurrency=concurrency,
                retries=2,
                allow_partial=True,
            )
            print(f"state             = {result.state}")
            print(f"expected_cases    = {result.expected_cases}")
            print(f"received          = {result.received}")
            print(f"failed            = {result.failed}")
            print(f"failed_case_ids   = {result.failed_case_ids}")
            if result.summary:
                agg = result.summary.get("aggregated_policies") or []
                print(f"aggregated policies: {len(agg)}")
            return 0

        if mode == "generate_only":
            project_id = ask("Project ID for generation", default=env_project_id)
            if not project_id:
                print("ERROR: project_id is required to generate a test.", file=sys.stderr)
                return 2

            test_name = ask("Test name", default=DEFAULT_TEST_NAME)
            use_images = ask_yes_no(
                "Enable image mode (image payloads for half of the cases)",
                default=False,
            )
            gen_kw: dict[str, Any] = {
                "project_id": project_id,
                "test_name": test_name or DEFAULT_TEST_NAME,
                "business_context": DEFAULT_BUSINESS_CONTEXT,
                "use_case": DEFAULT_USE_CASE,
                "certifications": DEFAULT_CERTIFICATIONS,
                "max_policies": DEFAULT_MAX_POLICIES,
                "max_prompts_per_policy": DEFAULT_MAX_PROMPTS_PER_POLICY,
            }
            if use_images:
                gen_kw["metadata"] = {"modes": {"image": True}}

            test_id = await client.generate_test(
                generate_kwargs=gen_kw,
            )
            print(f"generated test_id = {test_id}")
            return 0

        test_id = coerce_test_id(ask("Test ID to run", default=env_test_id))
        if not test_id:
            print("ERROR: test_id is required to run an existing test.", file=sys.stderr)
            return 2
        handshake = await client.call_agent(
            test_id=test_id,
            llm=call_llm,
            concurrency=concurrency,
            retries=2,
        )
        sched = await client.ensure_evaluation_from_client_responses(test_id)
        print(
            "Evaluation scheduling:",
            f"action={sched.action} reason={sched.reason} job_status={sched.job_status}",
        )
        await client.wait_for_evaluation_ready(
            test_id=test_id,
            skip_initial_ensure=True,
        )
        result = await client.get_eval_summary(
            test_id=test_id,
            expected_cases=handshake.expected_cases,
            allow_partial=True,
        )

    print(f"state             = {result.state}")
    print(f"expected_cases    = {result.expected_cases}")
    print(f"received          = {result.received}")
    print(f"failed            = {result.failed}")
    print(f"failed_case_ids   = {result.failed_case_ids}")
    if result.summary:
        agg = result.summary.get("aggregated_policies") or []
        print(f"aggregated policies: {len(agg)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
