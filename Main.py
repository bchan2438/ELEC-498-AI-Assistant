from Database_Code.ingest_data import load_swebench, transform_dataset, debug_print_example, connection, run_schema, insert_data
from LLM_Code.llm import rag_answer

def main(): 
    #debug_print_example()
    conn = connection()
    question = """ from typing import List, TypeVar

T = TypeVar("T")


def paginate(items: List[T], page: int, page_size: int) -> List[T]:
    if page < 1:
        raise ValueError("page must be >= 1")

    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    start = page * page_size
    end = start + page_size

    return items[start:end]"""
    print(rag_answer(conn, question))
    conn.close()


    #This function is only for the first time a device uses the code, so that the database will be pulled, embedded and stored locally. 
    #Once data has been stored locally, function is no longer needed and will waste API tokens if embedding is done more than once 
def grab_database(conn):
    insert_data(conn, "test") 



if __name__ == "__main__":
    main()