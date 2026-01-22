from Database_Code.ingest_data import load_swebench, transform_dataset, debug_print_example, connection, run_schema, insert_data


def main(): 
    #debug_print_example()
    conn = connection()
    # grab_database(conn)
    # print(rag_answer(conn, "Question"))
    conn.close()


    #This function is only for the first time a device uses the code, so that the database will be pulled, embedded and stored locally. 
    #Once data has been stored locally, function is no longer needed and will waste API tokens if embedding is done more than once 
def grab_database(conn):
    run_schema(conn)
    insert_data(conn, "test") 



if __name__ == "__main__":
    main()