import sys
from Database_Code.ingest_data import connection
from LLM_Code.llm import rag_answer

def main():
    # Called by the extension with 4 arguments:
    # sys.argv[1] = path to temp file containing the buggy code
    # sys.argv[2] = stderr/error string
    # sys.argv[3] = comma-separated error line numbers
    # sys.argv[4] = path to output file to write LLM response to

    if len(sys.argv) >= 5:
        # Called from the VS Code extension
        with open(sys.argv[1]) as f:
            code = f.read()

        error     = sys.argv[2]
        line_nums = sys.argv[3]
        out_file  = sys.argv[4]

        question = f"The following Python code has an error:\n\n{code}\n\nError:\n{error}\n\nError on lines: {line_nums}\n\nPlease explain the error and suggest a fix."

        conn = connection()
        result = rag_answer(conn, question)
        conn.close()

        with open(out_file, 'w') as f:
            f.write(result)

    else:
        # Called directly from the terminal (original behaviour)
        conn = connection()
        question = """from typing import List, TypeVar
...your test question here..."""
        print(rag_answer(conn, question))
        conn.close()

def grab_database(conn):
    from Database_Code.ingest_data import insert_data
    insert_data(conn, "test")

if __name__ == "__main__":
    main()