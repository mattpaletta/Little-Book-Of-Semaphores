import time
import humanfriendly


def merge_sort(lis):
    if len(lis) <= 1:
        yield from lis
    else:
        over = len(lis) // 2
        RL = merge_sort(lis[over:])
        LL = merge_sort(lis[:over])
        cRL = next(RL)
        cLL = next(LL)

        while True:
            if cRL is not None and cLL is not None and cRL <= cLL:
                try:
                    yield cRL
                    cRL = next(RL)
                except StopIteration:
                    cRL = None
            elif cLL is not None:
                try:
                    yield cLL
                    cLL = next(LL)
                except StopIteration:
                    cLL = None
            elif cRL is not None:
                yield cRL
                cRL = next(RL)
            else:
                yield cLL
                cLL = next(LL)

if __name__ == "__main__":
    lst = list(range(1, 1000000 + 1))
    print("Staring merge")
    start = time.time()
    x = merge_sort(list(lst))
    list(x)
    print(humanfriendly.format_timespan(time.time() - start))