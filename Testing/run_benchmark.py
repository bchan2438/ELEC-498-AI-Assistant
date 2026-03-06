import json
import time
import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Database_Code.ingest_data import connection
from Testing.llm_testing import rag_answer, retrieve_topk_debug, RAG_VERSION


def load_cases(path: str = "Testing/benchmark_cases.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print(f"Running benchmark with version: {RAG_VERSION}")

    cases = load_cases()
    conn = connection()
    results = []

    try:
        for case in cases:
            code = case["code"]
            error = case["error"]
            line_nums = case.get("line_nums", "")

            question = (
                f"The following Python code has an error:\n\n"
                f"{code}\n\n"
                f"Error:\n{error}\n\n"
                f"Error on lines: {line_nums}\n\n"
                f"Please explain the error and suggest a fix."
            )

            retrieval_start = time.time()
            retrieved_rows = retrieve_topk_debug(conn, code, error, k=5)
            retrieval_time = time.time() - retrieval_start

            answer_start = time.time()
            answer = rag_answer(conn, code, error, question, k=5)
            answer_time = time.time() - answer_start

            result = {
                "id": case["id"],
                "expected_category": case.get("expected_category"),
                "expected_keywords": case.get("expected_keywords", []),
                "retrieval_time_sec": round(retrieval_time, 4),
                "answer_time_sec": round(answer_time, 4),
                "retrieved": [
                    {
                        "instance_id": row[0],
                        "repo": row[1],
                        "distance": row[4],
                        "problem_statement_preview": row[2][:250],
                        "patch_preview": row[3][:250]
                    }
                    for row in retrieved_rows
                ],
                "answer": answer
            }

            results.append(result)

            print(f"Finished {case['id']}")

    finally:
        conn.close()

    with open("Testing/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\nSaved results to Testing/benchmark_results.json")


if __name__ == "__main__":
    main()