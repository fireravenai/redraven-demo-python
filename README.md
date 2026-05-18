# redraven-demo-python

Minimal end-to-end demo of the [RedRaven Python SDK](https://pypi.org/project/redraven/).

## Setup

Use [uv](https://docs.astral.sh/uv/). This demo pins **`redraven` to the local SDK checkout** next to this repo (`../redraven-sdk/packages/python`, editable) via `[tool.uv.sources]` in `pyproject.toml`.

```bash
uv sync
```

If you previously synced against PyPI, force the env to match the lockfile:

```bash
uv sync --reinstall-package redraven
```

To use the **published SDK** instead: in `pyproject.toml`, set `dependencies` to e.g. `redraven>=0.1.4` and **remove** the `[tool.uv.sources]` table, then run `uv lock && uv sync`.

## Configure .env


```
REDRAVEN_BASE_URL=https://api.redraven.fireraven.ai

# Your RedRaven API key found in Organization Settings in https://app.redraven.fireraven.ai
REDRAVEN_API_KEY=rr_...

# Your RedRaven Organization ID found in Organization Settings in https://app.redraven.fireraven.ai
REDRAVEN_ORGANIZATION_ID=<uuid of your RedRaven organization>

# Optional: set this (or enter it when prompted) -> found in Project Settings in https://app.redraven.fireraven.ai
REDRAVEN_PROJECT_ID=<uuid of a project in Redraven>

# Optional: set this (or enter it when prompted)
REDRAVEN_TEST_ID=<uuid of an existing test in Redraven>

# Optional, only if you want to run this demo with a basic OpenAI LLM
OPENAI_API_KEY=sk-...
```

## Run

```bash
uv run python main.py
```

The script is interactive: it asks whether to generate tests + run, run existing tests, or only generate tests, then prompts for IDs/concurrency (with env-based defaults). For “run existing” it uses `call_agent`, then `wait_for_evaluation_ready`, then `get_eval_summary` (same pattern as waiting for the dataset before reading results). `generate_and_run_test` bundles generate → agent → eval wait for mode 1.

Generated tests persist the generation metadata used by the RedRaven app, including business context, use case, certifications, specific policies, max policies, max prompts, and test modes. This keeps the Test Configuration modal and credits estimate in sync with the generated test.

The default `call_llm` calls the OpenAI API so you can wire up the flow with your OpenAI credentials (`OPENAI_API_KEY` in `.env`).
