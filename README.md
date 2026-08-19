# redraven-demo-python

Minimal end-to-end demo of [RedRaven](https://app.redraven.fireraven.ai) LLM red-teaming and policy evaluation through the [Python SDK](https://pypi.org/project/redraven/).

## Features

- **Interactive CLI**: Five modes — generate and run, run an existing test, generate only, reconnaissance loop, or attack loop
- **Test generation**: Aligns with the RedRaven app (business context, use case, certifications, policies, test modes)
- **Agent + evaluation flow**: `call_agent`, wait for evaluation, then `get_eval_summary` — or one-shot `generate_and_run_test`
- **Reconnaissance loop**: Fetch attack-surface probes, call your agent, submit responses for refusal evaluation
- **Attack loop**: Multi-turn red-team attacks via `/api/v2/…/attack-run`; auto-resumes an in-progress run on the test you choose
- **Example LLM integration**: Optional OpenAI-backed `call_llm` so you can try the full pipeline quickly
- **FireGuard bridge**: Export failing policies from results into FireGuard guardrails

## Documentation

- RedRaven app: https://app.redraven.fireraven.ai
- Python SDK docs: https://doc.fireraven.ai/redraven-sdk/python
- SDK overview: https://doc.fireraven.ai/redraven-sdk/overview

## Installation

1. **Clone or download this repository**

2. **Install dependencies with [uv](https://docs.astral.sh/uv/)**:

   ```bash
   uv sync
   ```

   To use the default OpenAI example in `call_llm`:

   ```bash
   uv sync --extra openai
   ```

3. **Create an account on RedRaven and set up your organization**
   - Go to https://app.redraven.fireraven.ai/ and create an account
   - Open **Organizations** and click **+ Create New Organization**

<!-- ![Organizations overview — empty state](images/image-00-org-landing.png) -->

   - After creation, your organization appears on the overview

![Organization created](images/image-01-org-created.png)

4. **Get your Organization ID and API key**
   - On the organization card, click **Settings**

![Organization settings entry](images/image-02-org-settings.png)

   - Copy the **Organization ID**
   - Under **API Keys**, click **+ Add API Key**, name it, and save the key (shown once)

![Generate API key](images/image-03-api-key.png)

5. **Purchase credits or subscribe**
   - In organization settings, open the **Plan** tab
   - RedRaven uses credits: **1 test case = 2 credits** (1 for prompt generation, 1 for response evaluation)
   - Without credits, a banner appears at the top of the app and tests cannot run

![Plan and credits](images/image-04-plan-credits.png)

6. **Create a project**
   - Go to **Projects** in the sidebar and click **+ Add Project**
   - Fill in name, description, and language, then click **+ Create**
   - Open the project **Settings** and copy the **Project ID**

![Create new project](images/image-05-create-project.png)

7. **Configure a test in the app (optional if you use SDK generation)**
   - Go to **Tests** and click **+ Run New Test**
   - Set test name, business context, AI agent use cases, test modes (Text, Image, etc.), certifications (e.g. HIPAA), and generation limits
   - Review the credit estimate, then click **Generate Test**

![Configure new test](images/image-06-configure-test.png)

   - When generation finishes, the test page shows **Generated** and displays the **Test ID** (copy it for SDK mode 2)

![Test dataset ready — waiting for SDK](images/image-07-test-dataset-ready.png)

8. **Set up your `.env` file**

   Create a `.env` file in the project directory:

   ```bash
   REDRAVEN_BASE_URL=https://api.redraven.fireraven.ai

   # From Organization Settings in https://app.redraven.fireraven.ai
   REDRAVEN_API_KEY=rr_...
   REDRAVEN_ORGANIZATION_ID=<uuid of your RedRaven organization>

   # Optional — prompted if unset (modes 1 and 3)
   REDRAVEN_PROJECT_ID=<uuid of a project in RedRaven>

   # Optional — prompted if unset (modes 2 and 5)
   REDRAVEN_TEST_ID=<uuid of an existing test in RedRaven>

   # Optional — only if you use the default OpenAI call_llm in main.py
   OPENAI_API_KEY=sk-...
   ```

9. **Configure test defaults in code (optional)**

   Edit the `DEFAULT_*` constants and `build_test_metadata()` / `build_generate_kwargs()` in `main.py` to match your scenario. These fields mirror the **Configure New Test** modal in the app (business context, use case, certifications, `max_policies`, `max_prompts_per_policy`, and modes such as text/image).

## Usage

Run the demo:

```bash
uv run python main.py
```

### Choose a mode

The script prompts for one of five modes:

| Mode | CLI choice | What it does |
|------|------------|----------------|
| Generate + run test | `1` | `client.generate_and_run_test(...)` — generate dataset, run your LLM on all cases, wait for evaluation, print summary |
| Call agent + run evaluation on existing test | `2` | `call_agent` → `ensure_evaluation_from_client_responses` → `wait_for_evaluation_ready` → `get_eval_summary` |
| Generate test only | `3` | `client.generate_test(...)` — returns `test_id` for a later run |
| Run reconnaissance loop | `4` | Fetch `metadata.reconnaissance.probes`, call your LLM per probe, `POST …/reconnaissance/evaluate` (refusal → `is_answered=false`) |
| Run attack loop | `5` | Multi-turn attack run via `attack-run/begin/next/turns/complete`; auto-resumes an in-progress run on the test you choose |

![CLI mode selection](images/image-08-sdk-cli.png)

You will be asked for **concurrency** (default `4`) and, depending on the mode, **Project ID** or **Test ID** (env vars are used as defaults when set).

Mode `4` requires a test whose reconnaissance probes are already `completed` (created best-effort when generating policies in the app).

Mode `5` requires a test with enabled scenarios and attack methods. Enter the **Test ID** (or set `REDRAVEN_TEST_ID`). If that test has an attack run still `running`, the demo skips `begin` and continues from the saved cursor; otherwise it starts a new run.

For mode `2`, after the SDK finishes you should see a summary similar to:

![SDK terminal output](images/image-09-sdk-output.png)

In the RedRaven app, the test page updates to **Evaluation complete** — click **View Results**:

![Evaluation complete in the app](images/image-10-eval-complete.png)

### Workflows

- **UI-first**: Create and generate a test in the app (steps 7–8 above), copy the **Test ID**, then run mode `2`.
- **SDK-first**: Set `REDRAVEN_PROJECT_ID` (or enter it when prompted) and use mode `1` or `3`. Mode `1` runs the full pipeline in one call; mode `3` only creates the test for a later run.

### Customize your agent

Replace `call_llm()` in `main.py` with your own LLM or agent. Your model API key stays in your process and is **never** sent to RedRaven.

The default implementation calls OpenAI `gpt-4o` when `OPENAI_API_KEY` is set and the `openai` extra is installed.

### Complex agent demo (`main_complex_agent.py`)

For a tool-using finance/insurance helper (Company1 Assist) instead of a bare chat completion:

```bash
uv sync --extra openai
uv run python main_complex_agent.py
```

Same RedRaven CLI modes as `main.py`, with Company1 business-context defaults. The agent uses OpenAI tool calling against simulated JSON data under `data/` (knowledge base, member DB with Bob/Alice/Roger, SQL accounts store). Member DB/KB/SQL tools intentionally do not enforce session-user parameter checks — useful for red-team evaluation of data-access and injection behaviors.

### SDK sequence (mode 2)

The expected sequence matches the app copy on the test page:

1. **Dataset ready** — generation completed (UI or `generate_test`)
2. **`call_agent`** — run your LLM on each case and submit responses
3. **`wait_for_evaluation_ready`** — block until scoring finishes
4. **`get_eval_summary`** — read pass/fail counts and policy aggregates

Mode `1` bundles these steps via `generate_and_run_test`.

## View results and remediate

1. **View test results**
   - From the test page, click **View Results**
   - See pass rate, breakdown by certification and policy, and recommendations

![Test results](images/image-11-results.png)

2. **Export policies to FireGuard**
   - In the recommendations sidebar, click **Export to FireGuard**
   - Use the same email on FireGuard; create or link your account, then click **Refresh Connection**

![FireGuard account required](images/image-12-export-fireguard.png)

   - Choose which projects receive the exported policies (or apply to all projects in the organization), then click **Continue**

![Select projects for export](images/image-13-export-fireguard-projects.png)

   - Review the export summary (policy count, organization, projects), then click **Export Policies**

![Export summary](images/image-14-export-fireguard-summary.png)

   - Exported policies appear in the FireGuard **Policies** page for use as input/output guardrails

![FireGuard policies](images/image-15-fireguard-policies.png)

3. **Generate a report**
   - On the results page, use **Preview Report** or **Download Report**

![Download report](images/image-16-report.png)

## Project Structure

- `main.py` — SDK demo, test metadata defaults, and `call_llm` example
- `main_complex_agent.py` — same RedRaven flow wired to the Company1 complex agent
- `complex_agent/` — system prompt, tool implementations, OpenAI tool loop
- `data/` — simulated knowledge base, member DB, and SQL accounts JSON
- `util.py` — CLI helpers (mode selection, prompts, test ID parsing)
- `pyproject.toml` — project metadata and dependencies
- `uv.lock` — locked dependency versions
- `images/` — screenshots referenced by this README
- `.env` — your API keys and IDs (create locally; not committed)

## Requirements

- Python 3.10+
- RedRaven API key and Organization ID
- RedRaven Project ID (for generation) and/or Test ID (for running an existing test)
- Optional: OpenAI API key (for the default `call_llm`)

## Dependencies

- `redraven>=0.1.5` — RedRaven Python SDK
- `httpx>=0.27` — HTTP client (SDK dependency)
- `python-dotenv>=1.0` — load `.env`
- `openai>=2.36.0` — optional (`uv sync --extra openai`) for the sample LLM
