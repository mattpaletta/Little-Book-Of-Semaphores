def barrier(gen, size):
    def real_decorator(original_func):
        def wrapper(*args, **kwargs):
            work = []
            my_iter = gen()
            for _ in range(size):
                work.append(my_iter.__next__())

            original_func(work, *args, **kwargs)
        return wrapper
    return real_decorator


def produce_work():
    yield from range(100)


@barrier(size = 10, gen = produce_work)
def group_by(work):
    print("Got work: {0}".format(", ".join(map(str, work))))


if __name__ == "__main__":
    group_by()
