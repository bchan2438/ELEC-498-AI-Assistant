# logic_error.py
# Purpose: runs without crashing, but produces the wrong result

def calculate_discount(price, discount_percent):
    # Intentional logic error:
    # should be price * (discount_percent / 100)
    return price * discount_percent

def main():
    price = 100
    discount_percent = 20
    final_price = price - calculate_discount(price, discount_percent)

    print(f"Original price: ${price}")
    print(f"Discount: {discount_percent}%")
    print(f"Final price: ${final_price}")  # Wrong result: -1900 instead of 80

if __name__ == "__main__":
    main()