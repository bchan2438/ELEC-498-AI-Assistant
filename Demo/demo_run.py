from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from Database_Code.ingest_data import connection
from LLM_Code.llm import rag_answer


def keyword_accuracy(answer: str, expected_keywords: List[str]) -> tuple[int, int, float, List[str]]:
    answer_lower = (answer or "").lower()
    matched = [kw for kw in expected_keywords if kw.lower() in answer_lower]
    total = len(expected_keywords)
    score = len(matched)
    pct = (score / total * 100.0) if total else 0.0
    return score, total, pct, matched


def main():
    demo_dir = Path(__file__).resolve().parent
    cases_path = demo_dir / "demo_cases.json"

    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    conn = connection()

    try:
        for case in cases:
            print("\n" + "=" * 90)
            print(f"CASE: {case['id']} | {case['description']}")
            print("=" * 90)

            code = case["code"]
            error = case["error"]
            line_nums = case["line_nums"]

            question = (
                f"The following Python code has an error:\n\n"
                f"{code}\n\n"
                f"Error:\n{error}\n\n"
                f"Error on lines: {line_nums}\n\n"
                f"Please explain the error and suggest a fix."
            )

            total_start = time.time()
            answer = rag_answer(conn, code, error, question)
            total_time = time.time() - total_start

            score, total, pct, matched = keyword_accuracy(
                answer,
                case.get("expected_answer_keywords", [])
            )

            print("\n[Final Answer]")
            print(answer)

            print("\n[Answer Accuracy]")
            print(f"Matched keywords: {matched}")
            print(f"Answer accuracy: {score}/{total} = {pct:.1f}%")

            print("\n[End-to-End Time]")
            print(f"Total time: {total_time:.2f}s")

    finally:
        conn.close()


if __name__ == "__main__":
    main()