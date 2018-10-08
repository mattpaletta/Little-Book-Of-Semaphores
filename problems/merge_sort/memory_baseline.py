import time

if __name__ == "__main__":
    print("Getting memory baseline for just array")
    lst = list(range(1, 10_000_000 + 1))
    time.sleep(20)
