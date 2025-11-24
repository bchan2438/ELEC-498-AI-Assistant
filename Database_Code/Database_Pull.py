from datasets import load_dataset
def Ingest_data():
    # Load lite database 
    sbl = load_dataset('SWE-bench/SWE-bench_Lite')
    # tests to ensure database is being pulled correctly. will be removed before final product 
    print(type(sbl))
    print(sbl)

    print(sbl['test'][50])

