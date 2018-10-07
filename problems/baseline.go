package main

import (
	"fmt"
	"math/big"
)

func main() {
    fmt.Println("Starting test")
	for j := 0; j < 1000; j++ {
		i := big.NewInt(int64(179425453+j))
		i.ProbablyPrime(100)
	    //fmt.Println(i)
	}
	fmt.Println("Done")
}
