# runtime_error.py
# Purpose: triggers a runtime error (division by zero)

def calculate_average(total, count):
    return total / count

def main():
    numbers = [10, 20, 30]
    total = sum(numbers)
    count = 0  # Intentional bug to trigger runtime error
    avg = calculate_average(total, count)
    print(f"Average: {avg}")

if __name__ == "__main__":
    main()