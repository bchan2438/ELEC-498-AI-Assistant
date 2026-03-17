nums = [2, 3, 4]
product = 1

for i in range(len(nums)):
    product *= i   # Should use nums[i]

print("Product:", product)   # Wrong result
