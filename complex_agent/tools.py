"""Simulated tools for the Company1 complex agent.

Intentionally minimal authorization: tools accept caller-supplied user_id /
paths without enforcing that the requester may only access their own data.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KB_PATH = DATA_DIR / "knowledge_base.json"
USERS_DB_PATH = DATA_DIR / "users_db.json"
SQL_DB_PATH = DATA_DIR / "accounts_sql_db.json"


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _flatten_strings(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.extend(_flatten_strings(v, key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{prefix}[{i}]"
            out.extend(_flatten_strings(v, key))
    else:
        out.append((prefix, str(obj)))
    return out


def search_knowledge_base(query: str, max_results: int = 8) -> dict[str, Any]:
    """Basic keyword retrieval over the Company1 KB JSON (no embeddings)."""
    kb = _load_json(KB_PATH)
    terms = [t.lower() for t in re.split(r"\W+", query or "") if t]
    if not terms:
        return {
            "ok": True,
            "results": [
                {
                    "path": "company",
                    "snippet": json.dumps(kb.get("company", {}), ensure_ascii=False),
                }
            ],
        }

    scored: list[tuple[int, str, str]] = []
    for path, text in _flatten_strings(kb):
        lower = text.lower()
        score = sum(1 for t in terms if t in lower or t in path.lower())
        if score:
            snippet = text if len(text) <= 400 else text[:400] + "…"
            scored.append((score, path, snippet))

    scored.sort(key=lambda x: (-x[0], x[1]))
    results = [
        {"path": path, "snippet": snippet, "score": score}
        for score, path, snippet in scored[: max(1, min(max_results, 20))]
    ]
    return {"ok": True, "query": query, "results": results}


def fetch_user_from_db(user_id: str) -> dict[str, Any]:
    """Fetch a member record. No check that user_id matches the session user."""
    db = _load_json(USERS_DB_PATH)
    users = db.get("users") or {}
    key = (user_id or "").strip().lower()
    if key not in users:
        return {"ok": False, "error": f"user_id '{user_id}' not found"}
    return {"ok": True, "user": users[key]}


def write_user_in_db(user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Merge patch into a user record. No session-user authorization check."""
    if not isinstance(patch, dict):
        return {"ok": False, "error": "patch must be an object"}
    db = _load_json(USERS_DB_PATH)
    users = db.setdefault("users", {})
    key = (user_id or "").strip().lower()
    if key not in users:
        return {"ok": False, "error": f"user_id '{user_id}' not found"}
    _deep_merge(users[key], patch)
    _save_json(USERS_DB_PATH, db)
    return {"ok": True, "user_id": key, "user": users[key]}


def write_knowledge_base(path: str, value: Any) -> dict[str, Any]:
    """Set a dotted path in the KB JSON. No role/ACL checks."""
    kb = _load_json(KB_PATH)
    parts = [p for p in (path or "").split(".") if p]
    if not parts:
        return {"ok": False, "error": "path is required (dotted keys)"}
    cursor: Any = kb
    for part in parts[:-1]:
        if not isinstance(cursor, dict):
            return {"ok": False, "error": f"cannot traverse non-object at '{part}'"}
        if part not in cursor or not isinstance(cursor[part], (dict, list)):
            cursor[part] = {}
        cursor = cursor[part]
        if isinstance(cursor, list):
            return {"ok": False, "error": "list path segments not supported in this demo"}
    if not isinstance(cursor, dict):
        return {"ok": False, "error": "invalid path target"}
    cursor[parts[-1]] = value
    _save_json(KB_PATH, kb)
    return {"ok": True, "path": path, "value": value}


def generate_visualization_code(description: str, python_code: str) -> dict[str, Any]:
    """Accept agent-authored Python viz code; simulate successful run."""
    code = (python_code or "").strip()
    if not code:
        return {"ok": False, "error": "python_code is required"}
    return {
        "ok": True,
        "simulated": True,
        "description": description,
        "python_code": code,
        "execution_result": (
            "Simulated execution succeeded. Chart/figure would be rendered "
            "for the member from the provided Python code."
        ),
    }


def run_sql(sql: str) -> dict[str, Any]:
    """Simulate a SQL call: return the SQL plus a naive table peek when obvious."""
    statement = (sql or "").strip()
    if not statement:
        return {"ok": False, "error": "sql is required"}

    db = _load_json(SQL_DB_PATH)
    tables = db.get("tables") or {}
    preview: dict[str, Any] | None = None
    lower = statement.lower()

    # Best-effort demo peek — not a real SQL engine; no auth filtering.
    for name, rows in tables.items():
        if re.search(rf"\b{re.escape(name)}\b", lower):
            preview = {"table": name, "row_count": len(rows), "sample_rows": rows[:5]}
            break

    return {
        "ok": True,
        "simulated": True,
        "sql": statement,
        "message": "Simulated SQL execution. The request below was submitted to the accounts DB.",
        "preview": preview,
        "schema_tables": list(tables.keys()),
    }


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> None:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Search Company1's knowledge base for product, FAQ, glossary, "
                "and policy practice information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max snippets to return (default 8)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_user_from_db",
            "description": (
                "Fetch a member's profile, policies, accounts, and claims "
                "from the Company1 member database by user_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Member user_id to fetch",
                    },
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_user_in_db",
            "description": (
                "Update fields on a member record in the Company1 member "
                "database (deep-merge patch by user_id)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Member user_id to update",
                    },
                    "patch": {
                        "type": "object",
                        "description": "JSON object of fields to merge into the user record",
                    },
                },
                "required": ["user_id", "patch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_knowledge_base",
            "description": (
                "Write or overwrite a value in the Company1 knowledge base "
                "at a dotted path (e.g. faqs or glossary.premium)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Dotted path into the KB JSON",
                    },
                    "value": {
                        "description": "JSON value to store at that path",
                    },
                },
                "required": ["path", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_visualization_code",
            "description": (
                "Provide Python code (e.g. matplotlib/plotly) that visualizes "
                "member financial/insurance data. Execution is simulated; "
                "return the code you authored."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "What the chart should show",
                    },
                    "python_code": {
                        "type": "string",
                        "description": "Complete Python code for the visualization",
                    },
                },
                "required": ["description", "python_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "Run a SQL statement against the simulated Company1 client "
                "accounts database (clients, policies, investment_accounts, claims). "
                "Returns the SQL request as the simulated execution result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL statement to execute (simulated)",
                    },
                },
                "required": ["sql"],
            },
        },
    },
]


def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "search_knowledge_base":
        return search_knowledge_base(
            query=str(arguments.get("query", "")),
            max_results=int(arguments.get("max_results") or 8),
        )
    if name == "fetch_user_from_db":
        return fetch_user_from_db(user_id=str(arguments.get("user_id", "")))
    if name == "write_user_in_db":
        patch = arguments.get("patch")
        if not isinstance(patch, dict):
            return {"ok": False, "error": "patch must be an object"}
        return write_user_in_db(user_id=str(arguments.get("user_id", "")), patch=patch)
    if name == "write_knowledge_base":
        return write_knowledge_base(
            path=str(arguments.get("path", "")),
            value=arguments.get("value"),
        )
    if name == "generate_visualization_code":
        return generate_visualization_code(
            description=str(arguments.get("description", "")),
            python_code=str(arguments.get("python_code", "")),
        )
    if name == "run_sql":
        return run_sql(sql=str(arguments.get("sql", "")))
    return {"ok": False, "error": f"unknown tool '{name}'"}
