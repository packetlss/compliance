package experiment

import (
	"bytes"
	"io"
	"os"
	"path/filepath"
	"sort"
	"syscall"
)

// Admit requires a persistent .admission.lock and cooperative exclusive writers.
// Shared lock covers every file read. No later resolver/evaluator file access occurs.
func Admit(root string) (Snapshot, error) { return admit(root, nil) }
func admit(root string, hook func()) (Snapshot, error) {
	var s Snapshot
	info, e := os.Lstat(root)
	if e != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return s, fail("admission root must be a real directory")
	}
	lock, e := os.OpenFile(filepath.Join(root, ".admission.lock"), os.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK, 0)
	if e != nil {
		return s, e
	}
	defer lock.Close()
	if info, e := lock.Stat(); e != nil || !info.Mode().IsRegular() {
		return s, fail("lock must be a regular persistent file")
	}
	if e = syscall.Flock(int(lock.Fd()), syscall.LOCK_SH|syscall.LOCK_NB); e != nil {
		return s, fail("admission busy: %w", e)
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	entries, e := os.ReadDir(root)
	if e != nil {
		return s, e
	}
	if len(entries) > MaxItems {
		return s, fail("input file count limit")
	}
	copies := map[string][]byte{}
	for _, entry := range entries {
		name := entry.Name()
		if name == ".admission.lock" {
			continue
		}
		if name != "inventory.json" && name != "evidence.json" && !(len(name) > 12 && name[:7] == "source-" && filepath.Ext(name) == ".json") {
			return s, fail("unexpected input %s", name)
		}
		b, e := boundedRead(filepath.Join(root, name))
		if e != nil {
			return s, e
		}
		copies[name] = b
	}
	if hook != nil {
		hook()
	}
	// Diagnostic only; the lock discipline, not a double read, provides coherence.
	for name, b := range copies {
		now, e := boundedRead(filepath.Join(root, name))
		if e != nil || !bytes.Equal(b, now) {
			return s, fail("input changed during admission: %s", name)
		}
	}
	if e = Decode(copies["inventory.json"], &s.Inventory); e != nil {
		return s, e
	}
	if e = Decode(copies["evidence.json"], &s.Evidence); e != nil {
		return s, e
	}
	names := []string{}
	for name := range copies {
		if name != "inventory.json" && name != "evidence.json" {
			names = append(names, name)
		}
	}
	sort.Strings(names)
	for _, name := range names {
		var source Source
		if e = Decode(copies[name], &source); e != nil {
			return s, fail("%s: %w", name, e)
		}
		s.Sources = append(s.Sources, source)
	}
	if len(s.Sources) == 0 {
		return s, fail("no policy sources")
	}
	return s, nil
}

func boundedRead(path string) ([]byte, error) {
	f, e := os.OpenFile(path, os.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK, 0)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	info, e := f.Stat()
	if e != nil || !info.Mode().IsRegular() || info.Size() > MaxBytes {
		return nil, fail("not a bounded regular input")
	}
	b, e := io.ReadAll(io.LimitReader(f, MaxBytes+1))
	if e != nil {
		return nil, e
	}
	if len(b) > MaxBytes {
		return nil, fail("input size limit")
	}
	return b, nil
}
