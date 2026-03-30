import argparse
import asyncio
import json
from pathlib import Path

from src.db import delete_copilot_session, get_copilot_session
from src.graphs.copilot_graph import copilot_chat_graph, copilot_init_graph


def load_cases(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def keyword_hit_ratio(text: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    hits = sum(1 for keyword in keywords if keyword and keyword in text)
    return hits / len(keywords)


async def run_case(case: dict):
    init_result = await copilot_init_graph.ainvoke({
        "raw_text": case["raw_text"],
        "source_pages": case.get("source_pages", []),
    })
    session_id = init_result["session_id"]
    session = get_copilot_session(session_id) or {}
    summary_data = session.get("summary_data", {}) or {}

    print(f"\n=== CASE: {case.get('name', session_id)} ===")
    print(f"Summary: {summary_data.get('summary', '')}")
    print(f"Takeaways: {summary_data.get('takeaways', [])}")
    print(f"Summary keyword hit ratio: {keyword_hit_ratio(summary_data.get('summary', ''), case.get('summary_keywords', [])):.2f}")

    for turn in case.get("questions", []):
        prepared = await copilot_chat_graph.ainvoke({
            "session_id": session_id,
            "user_query": turn.get("query", ""),
            "selected_text": turn.get("selected_text", ""),
            "quote_anchor": turn.get("quote_anchor", {}),
            "action": turn.get("action", "question"),
        })
        refs = prepared.get("references", [])
        print(f"\nQuestion: {turn.get('query') or turn.get('action')}")
        print(f"Intent: {prepared.get('reader_intent', '')}")
        print(f"Retrieval query: {prepared.get('retrieval_query', '')}")
        print(f"References: {[ref.get('section_title') for ref in refs]}")
        expected_sections = turn.get("expected_sections", [])
        if expected_sections:
            matched = sum(1 for item in expected_sections if item in [ref.get("section_title") for ref in refs])
            print(f"Section hit ratio: {matched / len(expected_sections):.2f}")

    if not case.get("keep_session", False):
        delete_copilot_session(session_id)


async def main():
    parser = argparse.ArgumentParser(description="Run lightweight evaluations for the reading copilot.")
    parser.add_argument("cases", help="Path to a JSON file containing eval cases.")
    args = parser.parse_args()

    cases = load_cases(Path(args.cases))
    for case in cases:
        await run_case(case)


if __name__ == "__main__":
    asyncio.run(main())
