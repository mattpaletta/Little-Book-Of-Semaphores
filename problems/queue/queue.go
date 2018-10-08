package main

import "fmt"

func do_work(done *chan int, j int, size_of_queue int) {
    sum := 0

    for i := 0; i < 10000; i++ {
		sum += i
	}

	*done <- j
}


func main() {
	size_of_queue := 10
    num_work := 1000

	my_queue := make(chan int, size_of_queue)

	for i := 0; i < num_work; i++ {
		go do_work(&my_queue, i, size_of_queue)
	}

    for i := 0; i < num_work; i++ {
    	fmt.Println(<- my_queue)
	}
}
