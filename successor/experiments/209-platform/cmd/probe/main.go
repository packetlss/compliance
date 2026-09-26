package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	exp "example.invalid/compliance/experiment209"
)

func run() error {
	args := os.Args[1:]
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if len(args) == 4 && args[0] == "assess" {
		s, e := exp.Admit(args[1])
		if e != nil {
			return e
		}
		p, e := exp.Resolve(s)
		if e != nil {
			return e
		}
		r, e := exp.Assess(ctx, p, s.Evidence, args[2])
		if e != nil {
			return e
		}
		if e = exp.Publish(args[3], r); e != nil {
			return e
		}
		fmt.Println("published", args[3])
		return nil
	}
	if len(args) == 2 && args[0] == "explain" {
		r, e := exp.ReadRecord(args[1])
		if e != nil {
			return e
		}
		s, e := exp.Explain(r)
		if e != nil {
			return e
		}
		b, e := exp.Encode(s)
		if e != nil {
			return e
		}
		fmt.Println(string(b))
		return nil
	}
	return fmt.Errorf("usage: probe assess INPUT_DIR UTC_TIME NEW_RECORD | probe explain RECORD")
}
func main() {
	if e := run(); e != nil {
		fmt.Fprintln(os.Stderr, "refused:", e)
		os.Exit(1)
	}
}
