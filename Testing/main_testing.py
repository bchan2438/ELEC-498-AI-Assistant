import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Database_Code.ingest_data import connection
from Testing.llm_testing import rag_answer, retrieve_topk_debug, RAG_VERSION


def main():
    code = """nums = [1, 2, 3]
print(nums(0))
"""

    error = "TypeError: 'list' object is not callable"
    line_nums = "2"

    question = (
        f"The following Python code has an error:\n\n"
        f"{code}\n\n"
        f"Error:\n{error}\n\n"
        f"Error on lines: {line_nums}\n\n"
        f"Please explain the error and suggest a fix."
    )

    conn = connection()

    try:
        print(f"Testing version: {RAG_VERSION}")
        print("\nTop retrieved rows:\n")

        rows = retrieve_topk_debug(conn, code, error, k=5)
        for i, row in enumerate(rows, start=1):
            instance_id, repo, problem_statement, patch, distance = row
            print(f"[{i}] instance_id={instance_id}")
            print(f"    repo={repo}")
            print(f"    distance={distance:.6f}")
            print(f"    problem_statement={problem_statement[:200].replace(chr(10), ' ')}")
            print()

        print("Model answer:\n")
        result = rag_answer(conn, code, error, question, k=5)
        print(result)

    finally:
        conn.close()


if __name__ == "__main__":
    main()