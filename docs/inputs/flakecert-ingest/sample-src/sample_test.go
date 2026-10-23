package sample

import (
	"math/rand"
	"os"
	"strconv"
	"testing"
)

func TestPass(t *testing.T) {
	if 1+1 != 2 {
		t.Fatal("math")
	}
}

func TestFailDeterministic(t *testing.T) {
	got, want := 1, 2
	if got != want {
		t.Fatalf("got %d want %d", got, want)
	}
}

func TestFlakySeeded(t *testing.T) {
	s, _ := strconv.ParseInt(os.Getenv("SEED"), 10, 64)
	if v := rand.New(rand.NewSource(s)).Float64(); v < 0.5 {
		t.Fatalf("seeded draw %.3f below threshold", v)
	}
}

func TestSkip(t *testing.T) { t.Skip("sample skip") }
