package main

import (
	"fmt"
	"time"
)

func run_barber(queue *chan int, num int, done *chan int) {
	for {
		i :=<- *queue
		fmt.Printf("Barber: %d, Serving customer %d\n", num, i)
		time.Sleep(time.Second * 1)
		*done <- i
	}
}

func run_customer(queue *chan int, num int) {
	for {
		fmt.Printf("Customer %d requesting barber\n", num)
		*queue <- num
	}
}

func main() {
	numBarbers := 3
	numCustomers := 100

	barberQueue := make(chan int, numBarbers)
	customerQueue := make(chan int, numCustomers)

	for i := 0; i < numBarbers; i++ {
		go run_barber(&customerQueue, i, &barberQueue)
	}

	for i := 0; i < numCustomers; i++ {
		//customerQueue <- i
		go run_customer(&customerQueue, i)
	}

	for i := 0; i < numCustomers; i++ {
		<- barberQueue
	}
}
