from Database_Code.ingest_data import load_swebench, transform_dataset, debug_print_example, connection, run_schema, insert_data
from LLM_Code.llm import rag_answer


def main(): 
    debug_print_example()
    conn = connection()
    run_schema(conn)
    insert_data(conn, "test")
    print(rag_answer(conn, "Question"))
    conn.close()



if __name__ == "__main__":
    main()