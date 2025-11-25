from datasets import load_dataset
def load_swebench(split):
    # Load lite database 
    sbl = load_dataset('SWE-bench/SWE-bench_Lite', split=split)
    
    return sbl

def transform_dataset(sbl):

    for row in sbl:
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

            "embedding": None,  
        }

def debug_print_example(split="test", idx=0):
    sbl = load_swebench(split)
    mapped = next(transform_dataset(sbl))
    print(mapped)