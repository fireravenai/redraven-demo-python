"""CLI helpers for the demo; not important for SDK usage, modify as needed."""
from __future__ import annotations

import asyncio
import re
from datetime import date
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import redraven
from tqdm import tqdm

_TEST_ID_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def coerce_test_id(raw: str) -> str:
    """Take the first UUID embedded in *raw* so pasted shell/log noise cannot become test_id."""
    s = (raw or "").strip()
    if not s:
        return ""
    m = _TEST_ID_UUID.search(s)
    return m.group(0) if m else s


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if raw:
        return raw
    return default or ""


def ask_yes_no(prompt: str, *, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(f"{prompt} ({hint}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


def default_test_name() -> str:
    """Default test name using today's date (e.g. Test 20260518)."""
    return f"Test {date.today().strftime('%Y%m%d')}"


CASE_COUNT_PRESETS: dict[str, dict[str, int]] = {
    "50": {"max_policies": 5, "max_prompts_per_policy": 2},
    # ~1000 cases: 1 cert × 20 policies × 10 prompts × 5 (jailbreak multiplier)
    "1000": {"max_policies": 20, "max_prompts_per_policy": 10},
}


def select_case_count_preset() -> dict[str, int]:
    print("Approximate dataset case count (1 certification, default demo settings):")
    print("  1) ~50 cases — default, fast iteration")
    print("  2) ~1000 cases — large load / stress test (generation and credits take much longer)")
    choice = ask("Enter choice", default="1")
    key = "1000" if choice == "2" else "50"
    preset = CASE_COUNT_PRESETS[key]
    print(
        f"Using max_policies={preset['max_policies']}, "
        f"max_prompts_per_policy={preset['max_prompts_per_policy']} (~{key} cases).",
        flush=True,
    )
    return dict(preset)


def select_mode() -> str:
    default = "1"
    print("Choose mode:")
    print("  1) Generate + run test")
    print(
        "     Step 1: server dataset generation (minutes; scales with case count). "
        "Step 2: agent run (throughput ≈ cases ÷ parallelism; echo ~20–30 cases/s at C=20 for ~50 cases). "
        "Step 3: evaluation wait (pipeline worker)."
    )
    print("  2) Call agent + run evaluation on existing test")
    print(
        "     Skips generation. Same Step 2 agent timing and Step 3 eval wait as mode 1."
    )
    print("  3) Generate test only (dataset generation; no agent or eval in this script)")
    print("  4) Run reconnaissance loop (probes → your LLM → evaluate refusals)")
    print(
        "     Requires a test with completed reconnaissance probes "
        "(e.g. after UI policy generation)."
    )
    choice = ask("Enter choice", default=default)
    if choice == "1":
        return "generate_run"
    if choice == "3":
        return "generate_only"
    if choice == "4":
        return "recon_loop"
    return "run_existing"


async def agent_run_resume_status(
    client: redraven.Client,
    test_id: str,
) -> tuple[str, int | None, int]:
    """Return a user-facing line plus (tqdm_total, tqdm_initial) for the agent LLM phase."""
    dataset_total: int | None = None
    try:
        ds = await client.get_results_summary(test_id, kind="dataset")
        cc = int((ds.manifest or {}).get("case_count") or 0)
        if cc > 0:
            dataset_total = cc
    except redraven.RedravenHTTPError:
        pass

    manifest = await client.get_agent_run_manifest(test_id)
    if manifest is not None and manifest.expected_cases > 0:
        done_ids = set(manifest.received_case_ids) | set(manifest.failed_case_ids)
        expected = manifest.expected_cases
        n_done = len(done_ids)
        pending = max(0, expected - n_done)
        msg = (
            f"Resuming agent run: {n_done}/{expected} case(s) already finished "
            f"({manifest.received} ok, {manifest.failed} failed). "
            f"Processing up to {pending} pending case(s); completed IDs are skipped."
        )
        return msg, expected, min(n_done, expected)

    if manifest is not None and manifest.expected_cases <= 0:
        if dataset_total:
            return (
                "Agent manifest exists but expected_cases is 0 (stale/empty); "
                f"using dataset case_count={dataset_total} for the progress bar.",
                dataset_total,
                0,
            )
        return (
            "Agent manifest exists but expected_cases is 0, and dataset case_count "
            "is not available; progress bar will count successful LLM calls only (no total).",
            None,
            0,
        )

    if dataset_total:
        return (
            f"Starting agent run: no client-response manifest yet ({dataset_total} cases in dataset).",
            dataset_total,
            0,
        )
    return (
        "Starting agent run: no client-response manifest yet (dataset size unknown until API materializes).",
        None,
        0,
    )


@asynccontextmanager
async def tqdm_agent_case_bar(
    llm: Callable[..., Awaitable[str]],
    *,
    desc: str,
    total: int | None = None,
    initial: int = 0,
) -> AsyncIterator[
    tuple[
        Callable[..., Awaitable[str]],
        Callable[[str, str], None],
    ]
]:
    """Pair ``(llm, on_case_terminal)`` for ``Client.call_agent``: one tqdm step per terminal case.

    ``on_case_terminal`` must be passed to ``call_agent(..., on_case_terminal=…)``.
    That advances the bar once per submitted client-response (ok or failed), not
    per LLM retry, so the bar can reach 100% when some cases exhaust retries.
    """
    bar_kw: dict[str, Any] = {
        "desc": desc,
        "unit": "case",
        "dynamic_ncols": True,
        "initial": max(0, initial),
    }
    if total is not None and total > 0:
        bar_kw["total"] = total
        bar_kw["bar_format"] = (
            "{desc}: {percentage:3.0f}%|{bar:12}| {n_fmt}/{total_fmt} "
            "[{elapsed}<{remaining}, {rate_fmt}]"
        )
    else:
        bar_kw["bar_format"] = (
            "{desc}: |{bar:12}| {n_fmt} [{elapsed}, {rate_fmt}]"
        )

    pbar = tqdm(**bar_kw)

    def on_case_terminal(_case_id: str, _status: str) -> None:
        pbar.update(1)

    try:
        yield llm, on_case_terminal
    finally:
        pbar.close()


# Match ``Client.generate_and_run_test`` / ``get_eval_summary`` defaults.
DEFAULT_POLL_INTERVAL_S = 2.0
DEFAULT_POLL_TIMEOUT_S = 600.0


async def demo_generate_run_with_progress(
    client: redraven.Client,
    *,
    generate_kwargs: dict[str, Any],
    llm: Callable[..., Awaitable[str]],
    concurrency: int,
    retries: int = 2,
    allow_partial: bool = True,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    poll_timeout_s: float = DEFAULT_POLL_TIMEOUT_S,
) -> Any:
    """Create test, wait for dataset, agent + tqdm, then eval summary (SDK-equivalent)."""
    print(
        "Step 1/3: Creating test and waiting for dataset generation (server-side)…",
        flush=True,
    )
    test_id = await client.generate_test(
        generate_kwargs=generate_kwargs,
        wait_for_dataset=True,
        poll_interval_s=poll_interval_s,
        poll_timeout_s=poll_timeout_s,
    )
    print(f"Dataset ready. test_id={test_id}", flush=True)

    resume_msg, bar_total, bar_initial = await agent_run_resume_status(client, test_id)
    print("Step 2/3: Agent run (your LLM)", flush=True)
    print(resume_msg, flush=True)

    async with tqdm_agent_case_bar(
        llm,
        desc="Generate+run · cases",
        total=bar_total,
        initial=bar_initial,
    ) as (bar_llm, on_case_terminal):
        handshake = await client.call_agent(
            test_id=test_id,
            llm=bar_llm,
            concurrency=concurrency,
            retries=retries,
            on_case_terminal=on_case_terminal,
        )

    print("Step 3/3: Waiting for evaluation and fetching summary…", flush=True)
    return await client.get_eval_summary(
        test_id=test_id,
        expected_cases=handshake.expected_cases,
        allow_partial=allow_partial,
        wait_for_completion=True,
        poll_interval_s=poll_interval_s,
        poll_timeout_s=poll_timeout_s,
    )


async def demo_run_existing_test_with_progress(
    client: redraven.Client,
    *,
    test_id: str,
    llm: Callable[..., Awaitable[str]],
    concurrency: int,
    retries: int = 2,
    allow_partial: bool = True,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    poll_timeout_s: float = DEFAULT_POLL_TIMEOUT_S,
) -> Any:
    """Resume line + tqdm, ``call_agent``, ensure eval, wait, summary (mode 2)."""
    print("Contacting API (dataset + agent-run status)…", flush=True)
    resume_msg, bar_total, bar_initial = await agent_run_resume_status(client, test_id)
    print(resume_msg, flush=True)

    async with tqdm_agent_case_bar(
        llm,
        desc="Agent · cases",
        total=bar_total,
        initial=bar_initial,
    ) as (bar_llm, on_case_terminal):
        handshake = await client.call_agent(
            test_id=test_id,
            llm=bar_llm,
            concurrency=concurrency,
            retries=retries,
            on_case_terminal=on_case_terminal,
        )
    sched = await client.ensure_evaluation_from_client_responses(test_id)
    print(
        "Evaluation scheduling:",
        f"action={sched.action} reason={sched.reason} job_status={sched.job_status}",
        flush=True,
    )
    await client.wait_for_evaluation_ready(
        test_id=test_id,
        skip_initial_ensure=True,
        poll_interval_s=poll_interval_s,
        poll_timeout_s=poll_timeout_s,
    )
    return await client.get_eval_summary(
        test_id=test_id,
        expected_cases=handshake.expected_cases,
        allow_partial=allow_partial,
    )


async def _backend_request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
) -> Any:
    """Call backend with the same env auth as the SDK.

    ``path`` may be ``/tests/...`` (defaults to ``/api/v1``) or a full
    ``/api/v1/...`` / ``/api/v2/...`` path.
    """
    import httpx
    from redraven.config import Settings

    settings = Settings.resolve(None, None, None)
    if path.startswith("/api/"):
        url = path
    else:
        url = f"/api/v1{path if path.startswith('/') else '/' + path}"
    async with httpx.AsyncClient(
        base_url=settings.base_url,
        headers={
            "X-API-Key": settings.api_key,
            "X-Organization-Id": settings.organization_id,
            "User-Agent": "redraven-demo-python/recon",
        },
        timeout=httpx.Timeout(60.0, connect=10.0),
    ) as http:
        resp = await http.request(method, url, json=json)
        if resp.status_code >= 400:
            detail: Any
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"{method} {url} failed ({resp.status_code}): {detail}")
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()


async def demo_recon_loop(
    *,
    test_id: str,
    llm: Callable[..., Awaitable[str]],
    concurrency: int = 4,
) -> dict[str, Any]:
    """Fetch recon probes, call the target LLM, submit for refusal evaluation."""
    print(f"Fetching test {test_id}…", flush=True)
    test = await _backend_request("GET", f"/tests/{test_id}")
    metadata = test.get("metadata") if isinstance(test, dict) else None
    if not isinstance(metadata, dict):
        metadata = {}
    recon = metadata.get("reconnaissance")
    if not isinstance(recon, dict):
        raise RuntimeError(
            "Test has no metadata.reconnaissance. "
            "Generate policies in the app first (probes are created best-effort)."
        )
    status = recon.get("status")
    probes = recon.get("probes") if isinstance(recon.get("probes"), list) else []
    if status != "completed" or not probes:
        raise RuntimeError(
            f"Reconnaissance probes not ready (status={status!r}, "
            f"probe_count={len(probes)}). Wait until status is 'completed'."
        )

    print(f"Running {len(probes)} reconnaissance probe(s) against your agent…", flush=True)
    sem = asyncio.Semaphore(max(1, concurrency))
    items: list[dict[str, Any]] = []

    async def _one(probe: dict[str, Any]) -> dict[str, Any]:
        prompt = probe.get("prompt") if isinstance(probe.get("prompt"), str) else ""
        probe_id = probe.get("id") if isinstance(probe.get("id"), str) else None
        async with sem:
            try:
                response = await llm(prompt)
            except TypeError:
                response = await llm(prompt, messages=None)
            if not isinstance(response, str):
                response = "" if response is None else str(response)
        return {
            "probe_id": probe_id,
            "request": prompt,
            "response": response,
        }

    gathered = await asyncio.gather(*[_one(p) for p in probes if isinstance(p, dict)])
    items.extend(gathered)

    print("Submitting responses for evaluation…", flush=True)
    result = await _backend_request(
        "POST",
        f"/api/v2/tests/{test_id}/reconnaissance/evaluate",
        json={"items": items},
    )
    return result if isinstance(result, dict) else {}
