import time
from multiprocessing.dummy import Pool
import humanfriendly

def blah(j):
    sum = 0
    for i in range(10000):
        sum += i

def avg(lst):
    return sum(lst) / len(lst)

if __name__ == "__main__":
    size_of_queue = 10
    num_items = 1000
    num_samples = 100

    time_taken = []
    for _ in range(num_samples):
        start = time.time()
        pool = Pool(processes = size_of_queue)
        pool.map(blah, range(num_items))
        pool.close()

        time_taken.append(time.time() - start)

    print("Done (threading)")
    print(humanfriendly.format_timespan(avg(time_taken)))