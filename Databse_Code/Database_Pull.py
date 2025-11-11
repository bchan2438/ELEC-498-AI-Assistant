from datasets import load_dataset
# Load lite variant
sbl = load_dataset('SWE-bench/SWE-bench_Lite')
print(type(sbl))
print(sbl)