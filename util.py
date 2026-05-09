"""CLI helpers for the demo; not important for SDK usage, modify as needed."""
from __future__ import annotations

import re

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


def select_mode() -> str:
    default = "1"
    print("Choose mode:")
    print("  1) Generate + run test")
    print("  2) Call agent + run evaluation on existing test")
    print("  3) Generate test only")
    choice = ask("Enter choice", default=default)
    if choice == "1":
        return "generate_run"
    if choice == "3":
        return "generate_only"
    return "run_existing"
