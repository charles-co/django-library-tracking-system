import random
rand_list = [random(1, 20) for _ in range(10)]

list_comprehension_below_10 = [num for num in rand_list if num < 10]

list_comprehension_below_10 = filter(lambda n: n < 10, rand_list)