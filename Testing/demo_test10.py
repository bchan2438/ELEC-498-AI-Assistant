nums = [1, 2, 3, 4, 5]
total = 0

for i in range(len(nums) - 1):
    total += nums[i]

print("Sum:", total)   # Should be 15, but prints 10