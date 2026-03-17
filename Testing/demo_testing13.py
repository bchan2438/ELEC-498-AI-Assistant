def add_item(item, my_list=[]):
    my_list.append(item)
    return my_list

print(add_item(1))
print(add_item(2))   # Unexpected: [1, 2]   