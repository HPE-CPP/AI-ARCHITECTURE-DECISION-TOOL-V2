#!/usr/bin/env python3
"""
Usage: python scripts/inspect_relevance.py --session-id <id>
       python scripts/inspect_relevance.py --filename <name>
       python scripts/inspect_relevance.py --sweep-clear-tier

Pulls relevance-gate decisions from the developer log for diagnosing
why specific documents passed or failed. Log path is auto-resolved
relative to this script so it works from any CWD.
"""
import json
import argparse
import os

# Resolve log path relative to this script's location (backend/scripts/ → backend/logs/)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_SCRIPT_DIR, "..", "logs", "relevance_gate.log")


def _iter_entries():
    """Yield parsed JSON entries from the log, skipping malformed lines."""
    if not os.path.exists(LOG_PATH):
        print(f"[ERROR] Log file not found: {LOG_PATH}")
        return
    with open(LOG_PATH, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {lineno} is not valid JSON ({e}), skipping.")


def find_entries(session_id: str | None, filename: str | None) -> list[dict]:
    matches = []
    for entry in _iter_entries():
        if session_id and entry.get("session_id") == session_id:
            matches.append(entry)
        elif filename and filename.lower() in entry.get("filename", "").lower():
            matches.append(entry)
    return matches


def print_breakdown(entry: dict) -> None:
    passed_str = "PASSED" if entry["passed"] else "REJECTED"
    print(f"\n{'=' * 64}")
    print(f"File    : {entry['filename']}")
    print(f"Session : {entry['session_id']}")
    print(f"Time    : {entry['timestamp']}")
    print(f"Result  : {passed_str}  (tier={entry['risk_tier']}, score={entry['total_risk_score']})")
    if entry.get("llm_review_performed"):
        print(
            f"LLM review: detected_type={entry.get('llm_detected_type')}, "
            f"confidence={entry.get('llm_confidence')}"
        )
    print(f"\nRule breakdown:")
    for flag in entry.get("rule_flags", []):
        marker = "!! TRIGGERED" if flag["triggered"] else "   ok       "
        print(
            f"  [{marker}] {flag['rule_name']:<22} +{flag['risk_points']:>3} pts"
            f"  — {flag['detail']}"
        )
    if entry.get("rejection_reason"):
        print(f"\nRejection reason: {entry['rejection_reason']}")
    print(f"{'=' * 64}\n")


def summarize_passed_at_clear() -> None:
    """
    Aggregate view of documents that passed at CLEAR tier (no LLM review
    at all) — the highest-risk group for Problem A, since these never
    got a semantic sanity check.
    """
    entries = [
        e for e in _iter_entries()
        if e.get("passed") and e.get("risk_tier") == "clear"
    ]

    if not entries:
        print("No documents found that passed at CLEAR tier.")
        return

    print(f"\n{len(entries)} document(s) passed at CLEAR tier (no LLM review):\n")
    for e in entries:
        flag_summary = ", ".join(
            f"{f['rule_name']}={f['risk_points']}"
            for f in e.get("rule_flags", [])
        )
        print(f"  {e['filename']:<42} score={e['total_risk_score']:>5}  [{flag_summary}]")

    print(
        "\nTip: documents that WRONGLY passed will appear here with score=0 across all rules.\n"
        "     Look for documents where 'category_coverage' and 'keyword_density' scored 0\n"
        "     despite the document not being a genuine requirements spec.\n"
    )


def list_all(limit: int = 50) -> None:
    """Print a compact summary of the last N log entries."""
    entries = list(_iter_entries())
    if not entries:
        print("No log entries found.")
        return
    tail = entries[-limit:]
    print(f"\nLast {len(tail)} entries (of {len(entries)} total):\n")
    header = f"{'Timestamp':<27} {'Session':<12} {'Result':<8} {'Tier':<12} {'Score':>5}  Filename"
    print(header)
    print("-" * len(header))
    for e in tail:
        passed_str = "PASSED" if e["passed"] else "REJECTED"
        print(
            f"{e['timestamp']:<27} {e['session_id']:<12} {passed_str:<8} "
            f"{e['risk_tier']:<12} {e['total_risk_score']:>5}  {e['filename']}"
        )
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Query the relevance-gate developer log to diagnose document pass/fail decisions."
    )
    parser.add_argument("--session-id", help="Look up a specific session by exact ID.")
    parser.add_argument("--filename", help="Look up entries containing this filename (case-insensitive substring).")
    parser.add_argument(
        "--sweep-clear-tier",
        action="store_true",
        help="Show all documents that passed at CLEAR tier (no LLM review) — the group most likely to contain wrongly-passed docs.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all recent log entries in a compact table.",
    )
    args = parser.parse_args()

    if args.sweep_clear_tier:
        summarize_passed_at_clear()
    elif args.list:
        list_all()
    elif args.session_id or args.filename:
        entries = find_entries(args.session_id, args.filename)
        if not entries:
            print("No matching log entries found.")
        else:
            for entry in entries:
                print_breakdown(entry)
    else:
        parser.print_help()
