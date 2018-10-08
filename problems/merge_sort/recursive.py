import time
import humanfriendly


def merge_rec(left, right):
    """Merge sort merging function."""

    left_index, right_index = 0, 0
    result = []
    while left_index < len(left) and right_index < len(right):
        if left[left_index] < right[right_index]:
            result.append(left[left_index])
            left_index += 1
        else:
            result.append(right[right_index])
            right_index += 1

    result += left[left_index:]
    result += right[right_index:]
    return result


def merge_sort_rec(array):
    """Merge sort algorithm implementation."""

    if len(array) <= 1:  # base case
        return array

    # divide array in half and merge sort recursively
    half = len(array) // 2
    left = merge_sort_rec(array[:half])
    right = merge_sort_rec(array[half:])

    return merge_rec(left, right)



if __name__ == "__main__":
    lst = list(range(1, 1000000 + 1))
    print("Staring merge")
    start = time.time()
    x = merge_sort_rec(list(lst))
    list(x)
    print(humanfriendly.format_timespan(time.time() - start))