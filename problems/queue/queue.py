import time
from multiprocessing.dummy import Pool
from multiprocessing import Pool as PPool
import humanfriendly

def blah(j):
    sum = 0
    for i in range(10000):
        sum += i

def avg(lst):
    return sum(lst) / len(lst)

if __name__ == "__main__":
    size_of_queue = 100
    num_items = 1000
    num_samples = 100

    time_taken = []
    for _ in range(num_samples):
        start = time.time()
        pool = Pool(processes = 10)
        pool.map(blah, range(num_items))
        pool.close()

        time_taken.append(time.time() - start)

    print("Done (threading)")
    print(humanfriendly.format_timespan(avg(time_taken)))

    time_taken = []
    for _ in range(num_samples):
        start = time.time()
        pool = PPool(processes = 10)
        pool.map(blah, range(num_items))
        pool.close()

        time_taken.append(time.time() - start)

    print("Done (processes)")
    print(humanfriendly.format_timespan(avg(time_taken)))
