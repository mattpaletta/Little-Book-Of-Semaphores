package main

import (
	"fmt"
	"os"
	"sync"
	"time"
)


// Inspired by: https://blog.ksub.org/bytes/2016/02/06/dining-savages/

type Pot struct {
	m sync.Mutex
	servings int
}

const TIMES_COOKED = 100
const M = 8

func (p Pot) potFull() bool {
	return p.servings == M
}

func (p Pot) potEmpty() bool {
	return p.servings == 0
}

type Savage struct {
	potEmpty *chan bool
	potFull *chan bool
	pot *Pot
}


func cook(potEmpty * chan bool, potFull *chan bool, pot *Pot) {
	num_cooked := 0
	for {
		// Wait until pot is empty
		<- *potEmpty
		fmt.Println("Cook preparing food.")
		// prepare food
		pot.servings = M
		// Alert the food is done.
		*potFull <- true
		num_cooked++
		if num_cooked > TIMES_COOKED {
			break
		}
	}
}

func (s Savage) eat() {
	for {
		s.pot.m.Lock()
		if s.pot.potEmpty() {
			// Wake the cook
			*s.potEmpty <- true
			// Wait unt il the pot is full
			<- *s.potFull
		}

		fmt.Println("Savage eating")
		time.Sleep(time.Second)

		s.pot.servings -= 1
		if s.pot.servings < 0 { fmt.Println("Error!"); os.Exit(1)}
		fmt.Println("Saving done eating")
		s.pot.m.Unlock()
	}
}

func main() {
	var empty = make(chan bool, M)
	var full = make(chan bool, M)
	var pot = Pot{}
	var savages [M]Savage


	for i := 0; i < M; i++ {
		savages[i] = Savage{potFull: &full, potEmpty: &empty, pot: &pot}

		// 1 of each savage eating
		go savages[i].eat()
	}

	// 1 cook
	cook(&empty, &full, &pot)
}
