package main

import (
	"fmt"
	"os"
	"sync"
)

type Pot2 struct {
	m sync.Mutex
	servings int
}

const M1 = 8
const NUM_COOKED = 1000

func (p Pot2) potFull() bool {
	return p.servings == M1
}

func (p Pot2) potEmpty() bool {
	return p.servings == 0
}

type Semaphore struct {
	m sync.Mutex
	val int
}


func (s *Semaphore) signal() {
	s.m.Lock()
	s.val++
	s.m.Unlock()
}

func (s *Semaphore) wait() {
	s.m.Lock()
	s.val--
	s.m.Unlock()

	for {
		s.m.Lock()
		if s.val == 0 {
			s.m.Unlock()
			break
		}
		s.m.Unlock()
	}
}

func putServingsInPot(pot *Pot2) {
	pot.servings = M1
}

func cook_signal(emptyPot *Semaphore, fullPot *Semaphore, pot *Pot2) {
	current_cooked := 0
	for {
		emptyPot.wait()
		fmt.Println("Cooking food")
		putServingsInPot(pot)
		fullPot.signal()
		current_cooked++
		if current_cooked >= NUM_COOKED {
			break
		}
	}
}

func savage_signal(m *sync.Mutex, emptyPot *Semaphore, fullPot *Semaphore, pot *Pot2) {
	for {
		m.Lock()
		if pot.potEmpty() {
			emptyPot.signal()
			fullPot.wait()
			pot.servings = M1
		}
		fmt.Println("Eating food.")
		pot.servings -= 1
		if pot.servings < 0 { fmt.Println("Error!"); os.Exit(1)}
		m.Unlock()
	}
}

func main() {
	pot := Pot2{}
	m := sync.Mutex{}
	full := Semaphore{}
	empty := Semaphore{}

	for i := 0; i < M1; i++ {
		// 1 of each savage eating
		go savage_signal(&m, &empty, &full, &pot)
	}

	// 1 cook
	cook_signal(&empty, &full, &pot)
}
