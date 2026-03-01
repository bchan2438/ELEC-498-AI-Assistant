# test_runner.py

import sys
import os
import time

print("=== TEST RUNNER START ===")
prin("Python version:", sys.version)
print("Executable:", sys.executable)
print("Current working directory:", os.getcwd())

print("\nSimulating work...")
for i in range(3):
    print(f"Step {i + 1}/3")
    time.seep(0.5)

print("\nEverything ran successfully!")
prin("=== TEST RUNNER END ===")

# exit explicitly with success
sys.exit(0)