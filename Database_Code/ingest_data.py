from datasets import load_dataset
import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2.extras import Json
from datetime import datetime
import json
import os
from Database_Code.embeddings import embed_text


# connects the postgresql database to this codebase 
def connection():
    conn = psycopg2.connect(
        dbname="swe_bench", # change to your database name if needed 
        user = "postgres", # change to your user if needed 
        password = "password", # change this to the password for postgres on your local machine 
        host = "localhost", #or host.docker.internal if you are using docker to run it 
        port = 5432, # This is the port that your postgres is running on you local machine. change if needed 
        
    )
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.commit()
    register_vector(conn) #for pgvector extension 
    
    return conn

def run_schema(conn):
    with conn.cursor() as cur:
        schema_path = os.path.join(os.path.dirname(__file__), "Schema.sql")
        with open(schema_path, "r") as f: 
            sql = f.read()
            cur.execute(sql)
    conn.commit()




def load_swebench(split):
    # Load lite database 
    sbl = load_dataset('SWE-bench/SWE-bench_Lite', split=split)
    
    return sbl


def make_embedding_text(row: dict) -> str:
    hint = row.get("hints_text") or ""
    return f"{row['problem_statement']}\n\nHints:\n{hint}".strip()


#function to transform raw data in to a easily manipulated state 
def transform_dataset(sbl, limit=1):
    for i, row in enumerate(sbl):
        if i >= limit:
            break

        text = make_embedding_text(row)
        emb = embed_text(text)
        
        yield {
            "instance_id": row["instance_id"],
            "repo": row["repo"],
            "base_commit": row["base_commit"],
            "version": row["version"],
            "environment_setup_commit": row["environment_setup_commit"],
            "problem_statement": row["problem_statement"],
            "hint": row["hints_text"],  
            "patch": row["patch"],
            "test_patch": row["test_patch"],
            "created_at": row["created_at"],
            "fail_to_pass": row["FAIL_TO_PASS"],
            "pass_to_pass": row["PASS_TO_PASS"],
            "embedding": emb,  
        }


# function to ensure that program is functioning as intended 
def debug_print_example(split="test", idx=0):
    sbl = load_swebench(split)
    mapped = next(transform_dataset(sbl, limit=1))

    # 🔍 TEMP DEBUG CHECKS
    print("Embedding type:", type(mapped["embedding"]))
    print("Embedding length:", len(mapped["embedding"]))
    print("First 5 values:", mapped["embedding"][:5])

    # Optional: see full row
    # print(mapped)

def parse_created_at(created_at_str: str):
    if not created_at_str:
        return None
    
    if created_at_str.endswith("Z"):
        created_at_str = created_at_str[:-1] + "+00:00"
    return datetime.fromisoformat(created_at_str)

# converts to JSONB 
def parse_json_list(s: str):
    if not s:
        return []
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return [s]


def insert_data(conn, split):
    sbl = load_swebench(split)

    with conn.cursor() as cur:
        for row in transform_dataset(sbl):

           
            fail_list = parse_json_list(row["fail_to_pass"])
            pass_list = parse_json_list(row["pass_to_pass"])

            cur.execute(
                """
                INSERT INTO swebench_data (
                    instance_id, repo, base_commit, version, environment_setup_commit,
                    problem_statement, hint, patch, test_patch, created_at,
                    fail_to_pass, pass_to_pass, embedding
                )
                VALUES (%s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s)
                ON CONFLICT (instance_id) DO NOTHING;
                """,
                (
                    row["instance_id"],
                    row["repo"],
                    row["base_commit"],
                    row["version"],
                    row["environment_setup_commit"],
                    row["problem_statement"],
                    row["hint"],
                    row["patch"],
                    row["test_patch"],
                    row["created_at"],
                    Json(fail_list),
                    Json(pass_list),
                    row["embedding"],
                )
            )

    conn.commit()





