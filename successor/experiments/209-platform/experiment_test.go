package experiment

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"
)

const t1 = "2026-09-26T12:00:00Z"

func fixture(t *testing.T) Snapshot {
	t.Helper()
	root := t.TempDir()
	entries, e := os.ReadDir("fixtures/input")
	if e != nil {
		t.Fatal(e)
	}
	for _, entry := range entries {
		b, e := os.ReadFile(filepath.Join("fixtures/input", entry.Name()))
		if e != nil {
			t.Fatal(e)
		}
		if e = os.WriteFile(filepath.Join(root, entry.Name()), b, 0600); e != nil {
			t.Fatal(e)
		}
	}
	os.WriteFile(filepath.Join(root, ".admission.lock"), nil, 0600)
	s, e := Admit(root)
	if e != nil {
		t.Fatal(e)
	}
	return s
}
func assess(t *testing.T, s Snapshot) (Plan, Record, Summary) {
	t.Helper()
	p, e := Resolve(s)
	if e != nil {
		t.Fatal(e)
	}
	r, e := Assess(context.Background(), p, s.Evidence, t1)
	if e != nil {
		t.Fatal(e)
	}
	sum, e := Explain(r)
	if e != nil {
		t.Fatal(e)
	}
	return p, r, sum
}
func outcome(t *testing.T, r Record, sub, check string) Outcome {
	t.Helper()
	for _, x := range r.Results {
		if x.Subject == sub {
			for _, o := range x.Outcomes {
				if o.Check == check {
					return o
				}
			}
		}
	}
	t.Fatal("missing outcome", sub, check)
	return Outcome{}
}
func subject(t *testing.T, p Plan, id string) SubjectPlan {
	t.Helper()
	for _, s := range p.Subjects {
		if s.Subject == id {
			return s
		}
	}
	t.Fatal("missing subject")
	return SubjectPlan{}
}
func setFact(s *Snapshot, id string, v any) {
	for i := range s.Evidence.Observations {
		if s.Evidence.Observations[i].ID == id {
			for k := range s.Evidence.Observations[i].Facts {
				s.Evidence.Observations[i].Facts[k] = v
			}
		}
	}
}
func wantRefusal(t *testing.T, s Snapshot) {
	t.Helper()
	if _, e := Resolve(s); e == nil {
		t.Fatal("expected resolution refusal")
	}
}
func TestStories1And2PersonaTrust(t *testing.T) {
	s := fixture(t)
	setFact(&s, "C-audit", true)
	setFact(&s, "C-groups", []any{"admins"})
	p, r, sum := assess(t, s)
	if sum.Status != "PASS" {
		t.Fatal(sum.Status)
	}
	if outcome(t, r, "C", "forward").Status != "PASS" || len(subject(t, p, "C").Checks) != 7 {
		t.Fatal("container checks")
	}
	sp := subject(t, p, "C")
	found := false
	for _, c := range sp.Checks {
		if c.Definition.ID == "forward" {
			found = len(c.Changes) == 1 && c.Changes[0].Change.Expected == json.Number("0") && c.Changes[0].Change.Value == json.Number("1") && c.Changes[0].Change.Approval != ""
		}
	}
	if !found {
		t.Fatal("tailoring attribution")
	}
	s = fixture(t)
	s.Inventory.Subjects[0].Classes = append(s.Inventory.Subjects[0].Classes, "container")
	wantRefusal(t, s)
	s = fixture(t)
	s.Evidence.Observations = append(s.Evidence.Observations, Observation{"S-runtime", "S", "observer", t1, map[string]any{"runtime": true}})
	p, _, _ = assess(t, s)
	for _, c := range subject(t, p, "S").Checks {
		if c.Definition.ID == "runtime" {
			t.Fatal("evidence selected persona")
		}
	}
	s = fixture(t)
	s.Inventory.Subjects = append(s.Inventory.Subjects, Subject{"Z", nil})
	s.Inventory.Selected = append(s.Inventory.Selected, "Z")
	p, _, sum = assess(t, s)
	if !subject(t, p, "Z").CoverageGap || sum.Status == "PASS" {
		t.Fatal("coverage disappeared")
	}
}
func TestStory3WaiverAndExclusionHistory(t *testing.T) {
	s := fixture(t)
	p, r, _ := assess(t, s)
	o := outcome(t, r, "C", "audit")
	if o.Status != "WAIVED" || o.Underlying != "FAIL" || o.Waiver.Approval == "" {
		t.Fatal(o)
	}
	if len(subject(t, p, "C").Exclusions) != 1 {
		t.Fatal("exclusion lost")
	}
	for _, o := range r.Results[0].Outcomes {
		if o.Check == "E" {
			t.Fatal("excluded check evaluated")
		}
	}
	for i := range s.Evidence.Observations {
		s.Evidence.Observations[i].At = "2026-09-28T12:00:00Z"
	}
	later, e := Assess(context.Background(), p, s.Evidence, "2026-09-28T12:00:00Z")
	if e != nil {
		t.Fatal(e)
	}
	if outcome(t, later, "C", "audit").Status != "FAIL" {
		t.Fatal("expired waiver")
	}
	if _, e = Explain(r); e != nil || outcome(t, r, "C", "audit").Status != "WAIVED" {
		t.Fatal("history changed", e)
	}
	for _, mode := range []string{"missing", "invalid", "error"} {
		s := fixture(t)
		switch mode {
		case "missing":
			s.Evidence.Observations = nil
		case "invalid":
			setFact(&s, "C-audit", json.Number("0"))
		case "error":
			s.Sources[0].Checks[2].Module = "package criterion\ndecision := 1"
		}
		_, r, _ := assess(t, s)
		o := outcome(t, r, "C", "audit")
		if o.Status == "WAIVED" {
			t.Fatal("waiver cured", mode)
		}
	}
}
func TestStories4And5ObjectivesParameters(t *testing.T) {
	s := fixture(t)
	p, r, sum := assess(t, s)
	if sum.Objectives["C/access"] != "FAIL" {
		t.Fatal(sum.Objectives)
	}
	for _, id := range []string{"central", "groups", "audit"} {
		outcome(t, r, "C", id)
	}
	if subject(t, p, "C").Objectives[0].Definition.Baseline != "company-access" {
		t.Fatal("group lost")
	}
	for _, mode := range []string{"zero", "not-implemented", "not-applicable", "multiple", "missing-child", "unexpected-child"} {
		t.Run(mode, func(t *testing.T) {
			s := fixture(t)
			src := &s.Sources[2]
			switch mode {
			case "zero":
				src.Assignments[0].Realizations = nil
			case "not-implemented", "not-applicable":
				src.Realizations[0].State = mode
				src.Realizations[0].Checks = nil
				src.Realizations[0].Reason = "review"
				src.Realizations[0].Approval = "approval"
			case "multiple":
				r := src.Realizations[0]
				r.ID = "second"
				src.Realizations = append(src.Realizations, r)
				src.Assignments[0].Realizations = append(src.Assignments[0].Realizations, r.ID)
				wantRefusal(t, s)
				return
			}
			p, r, sum := assess(t, s)
			if mode == "zero" || mode == "not-implemented" {
				if !subject(t, p, "C").Objectives[0].Gap || sum.Status == "PASS" {
					t.Fatal("gap")
				}
			}
			if mode == "not-applicable" && sum.Objectives["C/access"] != "NOT_APPLICABLE" {
				t.Fatal("N/A")
			}
			if mode == "missing-child" {
				r.Results[0].Outcomes = r.Results[0].Outcomes[1:]
				if ValidateRecord(r) == nil {
					t.Fatal("truncated accepted")
				}
			}
			if mode == "unexpected-child" {
				r.Results[0].Outcomes[0].Check = "unexpected"
				if ValidateRecord(r) == nil {
					t.Fatal("unexpected accepted")
				}
			}
		})
	}
	for _, mode := range []string{"missing", "type", "target", "parent-revision", "expected", "interface"} {
		t.Run(mode, func(t *testing.T) {
			s := fixture(t)
			switch mode {
			case "missing":
				delete(s.Sources[0].Parameters[0].Values, "seconds")
			case "type":
				s.Sources[0].Parameters[0].Values["seconds"] = true
			case "target":
				s.Sources[0].Checks[0].Freshness.Key = "absent"
			case "parent-revision":
				s.Sources[0].Policies[1].Parent.Revision = "old"
			case "expected":
				s.Sources[0].Policies[1].Changes[0].Expected = json.Number("2")
			case "interface":
				s.Sources[0].Checks[0].DesiredLink = Link{"timing", "seconds", "boolean"}
			}
			wantRefusal(t, s)
		})
	}
	for _, sp := range p.Subjects {
		for _, c := range sp.Checks {
			if c.FreshSeconds != 3600 {
				t.Fatal("freshness fanout")
			}
		}
	}
	s = fixture(t)
	s.Sources[0].Assignments[1].Parameters = append(s.Sources[0].Assignments[1].Parameters, "software-container")
	c := s.Sources[0].Checks[3]
	c.ValueType = "strings"
	c.DesiredLink = Link{"software-container", "allowed", "strings"}
	s.Sources[0].Checks[3] = c
	p, e := Resolve(s)
	if e != nil {
		t.Fatal(e)
	}
	for _, c := range subject(t, p, "C").Checks {
		if c.Definition.ID == "runtime" && !equal(c.Desired, []any{"audit-agent", "container-runtime"}) {
			t.Fatal("complete software value")
		}
	}
	s.Sources[0].Parameters[2].Expected["allowed"] = []any{"wrong"}
	wantRefusal(t, s)
}
func TestStory6EvidenceAndRefusal(t *testing.T) {
	for _, mode := range []string{"missing", "stale", "invalid", "ambiguous", "negative", "duplicate", "error", "malformed", "inconclusive"} {
		t.Run(mode, func(t *testing.T) {
			s := fixture(t)
			want := "UNKNOWN"
			switch mode {
			case "missing":
				s.Evidence.Observations = nil
			case "stale":
				for i := range s.Evidence.Observations {
					s.Evidence.Observations[i].At = "2026-09-20T12:00:00Z"
				}
			case "invalid":
				setFact(&s, "S-forward", false)
			case "ambiguous":
				s.Evidence.Observations = append(s.Evidence.Observations, Observation{"conflict", "S", "synthetic-observer", t1, map[string]any{"forward": json.Number("1")}})
			case "negative":
				setFact(&s, "S-forward", json.Number("1"))
				want = "FAIL"
			case "duplicate":
				o := s.Evidence.Observations[0]
				o.ID = "duplicate"
				s.Evidence.Observations = append([]Observation{o}, s.Evidence.Observations...)
				want = "PASS"
			case "error":
				s.Sources[0].Checks[0].Module = "package criterion\ndecision := {\"satisfied\": 1/0 == 0, \"conclusive\": true}"
				want = "ERROR"
			case "malformed":
				s.Sources[0].Checks[0].Module = "package criterion\ndecision := true"
				want = "ERROR"
			case "inconclusive":
				s.Sources[0].Checks[0].Module = "package criterion\ndecision := {\"satisfied\": false, \"conclusive\": false}"
			}
			_, r, _ := assess(t, s)
			if o := outcome(t, r, "S", "forward"); o.Status != want {
				t.Fatal(mode, o)
			}
			if mode == "duplicate" {
				for i, j := 0, len(s.Evidence.Observations)-1; i < j; i, j = i+1, j-1 {
					s.Evidence.Observations[i], s.Evidence.Observations[j] = s.Evidence.Observations[j], s.Evidence.Observations[i]
				}
				_, rr, _ := assess(t, s)
				if !equal(outcome(t, r, "S", "forward"), outcome(t, rr, "S", "forward")) {
					t.Fatal("order winner")
				}
			}
		})
	}
	s := fixture(t)
	p, e := Resolve(s)
	if e != nil {
		t.Fatal(e)
	}
	s.Evidence.Observations = append(s.Evidence.Observations, s.Evidence.Observations[0])
	s.Evidence.Observations[len(s.Evidence.Observations)-1].Collector = "conflict"
	r, e := Assess(context.Background(), p, s.Evidence, t1)
	if e == nil || len(r.Results) != 0 {
		t.Fatal("shared prerequisite did not refuse")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, e = Assess(ctx, p, Evidence{}, t1); e == nil {
		t.Fatal("cancelled shared prerequisite")
	}
}
func TestStories7And8Records(t *testing.T) {
	s := fixture(t)
	s.Inventory.Subjects = append(s.Inventory.Subjects, Subject{"Z", []string{"standard"}})
	s.Inventory.Selected = append(s.Inventory.Selected, "Z")
	_, r, _ := assess(t, s)
	r.Results = r.Results[:2]
	sum, e := Explain(r)
	if e != nil || sum.Subjects != 3 || !equal(sum.Missing, []string{"Z"}) || sum.Status == "PASS" {
		t.Fatal(sum, e)
	}
	for _, mode := range []string{"operation", "plan", "subject", "duplicate", "evidence", "waiver", "slots"} {
		t.Run(mode, func(t *testing.T) {
			_, r, _ := assess(t, fixture(t))
			switch mode {
			case "operation":
				r.Results[0].Operation = "foreign"
			case "plan":
				r.Results[0].Plan = "foreign"
			case "subject":
				r.Results[0].Subject = "S"
			case "duplicate":
				rr := r.Results[0]
				rr.At = "2026-09-26T12:00:01Z"
				r.Results = append(r.Results, rr)
			case "evidence":
				r.Results[0].Outcomes[0].Selected = nil
			case "waiver":
				for i := range r.Results[0].Outcomes {
					if r.Results[0].Outcomes[i].Status == "WAIVED" {
						r.Results[0].Outcomes[i].Waiver = nil
					}
				}
			case "slots":
				r.Plan.Slots = r.Plan.Slots[:1]
			}
			if _, e := Explain(r); e == nil {
				t.Fatal("invalid retained record accepted")
			}
		})
	}
	_, r, _ = assess(t, fixture(t))
	path := filepath.Join(t.TempDir(), "record.json")
	if e = Publish(path, r); e != nil {
		t.Fatal(e)
	}
	if e = Publish(path, r); e != nil {
		t.Fatal("safe retry", e)
	}
	rr, e := ReadRecord(path)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = Explain(rr); e != nil {
		t.Fatal(e)
	}
	r.Results[0].ID = "different"
	if Publish(path, r) == nil {
		t.Fatal("overwrite")
	}
	path = filepath.Join(t.TempDir(), "interrupted.json")
	if e = publish(path, r, func() error { return fail("interruption") }); e == nil {
		t.Fatal("interruption")
	}
	if _, e = os.Stat(path); !os.IsNotExist(e) {
		t.Fatal("partial public result")
	}
	if e = Publish(path, r); e != nil {
		t.Fatal("reattempt", e)
	}
}
func TestTypedJSON(t *testing.T) {
	for _, input := range []string{`{"ID":"a","ID":"b"}`, `{"id":"a"}`, `{"ID":null}`, `{"ID":1.0}`, `{"ID":9007199254740992}`, `{"ID":1e2}`, `{"ID":"x"} {}`, `{"ID":"x","Unknown":1}`} {
		var x Subject
		if Decode([]byte(input), &x) == nil {
			t.Fatal("accepted", input)
		}
	}
	for _, input := range []string{`{"v":true}`, `{"v":1}`, `{"v":-9007199254740991}`, `{"v":["b","a"]}`} {
		var x map[string]any
		if e := Decode([]byte(input), &x); e != nil {
			t.Fatal(e)
		}
	}
	if typed(true, "integer") || equal(true, json.Number("1")) || equal([]any{"a", "b"}, []any{"b", "a"}) {
		t.Fatal("typed equality")
	}
	for _, x := range []string{"2026-09-26", "2026-09-26T12:00:00+00:00", "2026-09-26T12:00:00.1Z"} {
		if _, e := stamp(x); e == nil {
			t.Fatal("timestamp accepted")
		}
	}
}
func TestAdmissionMutationAndIsolation(t *testing.T) {
	s := fixture(t)
	root := t.TempDir()
	write := func(name string, v any) {
		b, e := Encode(v)
		if e != nil {
			t.Fatal(e)
		}
		if e = os.WriteFile(filepath.Join(root, name), b, 0600); e != nil {
			t.Fatal(e)
		}
	}
	write("inventory.json", s.Inventory)
	write("evidence.json", s.Evidence)
	for _, src := range s.Sources {
		write("source-"+src.Name+".json", src)
	}
	lock, e := os.OpenFile(filepath.Join(root, ".admission.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if e != nil {
		t.Fatal(e)
	}
	defer lock.Close()
	if e = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); e != nil {
		t.Fatal(e)
	}
	if _, e = Admit(root); e == nil {
		t.Fatal("writer contention accepted")
	}
	syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	admitted, e := admit(root, func() {
		if e = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); e == nil {
			t.Fatal("writer entered shared admission")
		}
	})
	if e != nil {
		t.Fatal(e)
	}
	for _, file := range []string{"source-core.json", "evidence.json", "inventory.json"} {
		old, _ := os.ReadFile(filepath.Join(root, file))
		_, e = admit(root, func() { os.WriteFile(filepath.Join(root, file), []byte("{}"), 0600) })
		if e == nil {
			t.Fatal("observed in-flight mutation not rejected", file)
		}
		os.WriteFile(filepath.Join(root, file), old, 0600)
	}
	os.RemoveAll(root)
	_, _, sum := assess(t, admitted)
	if sum.Status != "FAIL" {
		t.Fatal("snapshot reread files")
	}
}
func TestEvaluatorBoundaryAndCancellation(t *testing.T) {
	for _, expr := range []string{`http.send({"method":"GET","url":"http://127.0.0.1:1"})`, `net.lookup_ip_addr("example.com")`, `time.now_ns()`, `rand.intn("x",10)`, `uuid.rfc4122("x")`} {
		status, _ := Evaluate(context.Background(), "package criterion\ndecision := "+expr, map[string]any{})
		if status != "ERROR" {
			t.Fatal("forbidden builtin", expr, status)
		}
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	start := time.Now()
	status, _ := Evaluate(ctx, "package criterion\ndecision := true", nil)
	if status != "ERROR" || time.Since(start) > time.Second {
		t.Fatal("cancellation")
	}
	status, _ = Evaluate(context.Background(), strings.Repeat("x", 16385), nil)
	if status != "ERROR" {
		t.Fatal("module limit")
	}
	// Deliberately expensive cross product under the allowlist; deadline must interrupt.
	a := make([]any, 10000)
	for i := range a {
		a[i] = json.Number("1")
	}
	start = time.Now()
	status, diag := Evaluate(context.Background(), "package criterion\ndecision := {\"conclusive\": true, \"satisfied\": count([1 | x := input.a[_]; y := input.a[_]; x == y]) == 0}", map[string]any{"a": a})
	if status != "ERROR" || !strings.Contains(diag, "execution") || time.Since(start) > 3*time.Second {
		t.Fatal("bounded evaluation", status, diag, time.Since(start))
	}
	t.Log("cancelled cross-product in", time.Since(start))
}
func TestSourceOrderAndConflicts(t *testing.T) {
	s := fixture(t)
	p, _, _ := assess(t, s)
	s.Sources[0], s.Sources[2] = s.Sources[2], s.Sources[0]
	pp, _, _ := assess(t, s)
	p.ID = pp.ID
	p.Operation = pp.Operation
	if !equal(p, pp) {
		t.Fatal("source order")
	}
	s.Sources = append(s.Sources, s.Sources[0])
	assess(t, s)
	dup := s.Sources[0]
	dup.Revision = "divergent"
	s.Sources = append(s.Sources, dup)
	wantRefusal(t, s)
}

func TestConservativeObjectiveAndParameterOnly(t *testing.T) {
	for _, mode := range []string{"all-na", "gap-with-passing-technical", "parameter-only", "group-dag"} {
		t.Run(mode, func(t *testing.T) {
			s := fixture(t)
			switch mode {
			case "all-na":
				s.Inventory.Selected = []string{"C"}
				s.Inventory.Subjects[1].Classes = []string{"access"}
				r := &s.Sources[2].Realizations[0]
				r.State = "not-applicable"
				r.Checks = nil
				r.Reason = "reviewed"
				r.Approval = "approval"
			case "gap-with-passing-technical":
				setFact(&s, "C-audit", true)
				setFact(&s, "C-groups", []any{"admins"})
				s.Sources[2].Assignments[0].Realizations = nil
			case "parameter-only":
				s.Inventory.Selected = []string{"S"}
				s.Sources[0].Assignments[0].Policies = nil
				s.Sources[1].Assignments = nil
			case "group-dag":
				s.Inventory.Groups = append(s.Inventory.Groups, Group{"leaf-a", "leaf-a", []string{"standard"}}, Group{"leaf-b", "leaf-b", []string{"standard"}})
				s.Inventory.Subjects[0].Classes = []string{"leaf-a", "leaf-b"}
			}
			p, _, summary := assess(t, s)
			if mode != "group-dag" && summary.Status == "PASS" {
				t.Fatal("manufactured success", mode)
			}
			if mode == "group-dag" && len(subject(t, p, "S").Checks) != 5 {
				t.Fatal("DAG duplicated subject checks")
			}
		})
	}
	for _, pair := range []struct {
		values []string
		want   string
	}{{[]string{"FAIL", "ERROR", "UNKNOWN", "WAIVED"}, "FAIL"}, {[]string{"ERROR", "UNKNOWN", "WAIVED"}, "ERROR"}, {[]string{"UNKNOWN", "WAIVED"}, "UNKNOWN"}, {[]string{"PASS", "WAIVED"}, "WAIVED"}, {[]string{"PASS", "PASS"}, "PASS"}} {
		if rollup(pair.values) != pair.want {
			t.Fatal("conservative outcome ordering")
		}
	}
}
func TestAdmissionModuleSchemaMutationsAndFileBounds(t *testing.T) {
	s := fixture(t)
	root := t.TempDir()
	save := func(name string, v any) {
		b, e := Encode(v)
		if e != nil {
			t.Fatal(e)
		}
		if e = os.WriteFile(filepath.Join(root, name), b, 0600); e != nil {
			t.Fatal(e)
		}
	}
	os.WriteFile(filepath.Join(root, ".admission.lock"), nil, 0600)
	save("inventory.json", s.Inventory)
	save("evidence.json", s.Evidence)
	for _, src := range s.Sources {
		save("source-"+src.Name+".json", src)
	}
	for _, mode := range []string{"module", "schema"} {
		src := s.Sources[0]
		b, _ := Encode(src)
		var copy Source
		Decode(b, &copy)
		if _, e := admit(root, func() {
			if mode == "module" {
				copy.Checks[0].Module = "package criterion\ndecision := false"
			} else {
				copy.Checks[0].Schema["forward"] = "boolean"
			}
			save("source-core.json", copy)
		}); e == nil {
			t.Fatal("in-flight source mutation accepted", mode)
		}
		save("source-core.json", src)
	}
	admitted, e := Admit(root)
	if e != nil {
		t.Fatal(e)
	}
	save("source-core.json", Source{Name: "removed"})
	assess(t, admitted)
	os.Remove(filepath.Join(root, "source-core.json"))
	os.Symlink("evidence.json", filepath.Join(root, "source-core.json"))
	if _, e = Admit(root); e == nil {
		t.Fatal("symlink admitted")
	}
	os.Remove(filepath.Join(root, "source-core.json"))
	os.WriteFile(filepath.Join(root, "source-core.json"), []byte(strings.Repeat("x", MaxBytes+1)), 0600)
	if _, e = Admit(root); e == nil {
		t.Fatal("oversized input admitted")
	}
}

func TestUnicodeValueBoundary(t *testing.T) {
	for _, s := range []string{`{"x":"\ud800"}`, `{"x":"\udfff"}`, `{"x":"\ud800\u0041"}`, `{"x":-0}`} {
		var x map[string]any
		if Decode([]byte(s), &x) == nil {
			t.Fatal("unsupported value", s)
		}
	}
	for _, s := range []string{`{"x":"\ud83d\ude00"}`, `{"x":"\\ud800"}`} {
		var x map[string]any
		if e := Decode([]byte(s), &x); e != nil {
			t.Fatal(e)
		}
	}
}

func TestReviewDeterministicTailoringAndWaiverIdentity(t *testing.T) {
	s := fixture(t)
	other := s.Sources[0].Policies[1]
	other.ID = "another-container"
	other.Changes = append([]Change{}, other.Changes...)
	other.Changes[0].Reason = "independent approved routing"
	other.Changes[0].Approval = "review-alternative"
	s.Sources[0].Policies = append(s.Sources[0].Policies, other)
	s.Sources[0].Assignments[1].Policies = append(s.Sources[0].Assignments[1].Policies, other.ID)
	var expected []AppliedChange
	for i := 0; i < 100; i++ {
		p, e := Resolve(s)
		if e != nil {
			t.Fatal(e)
		}
		for _, c := range subject(t, p, "C").Checks {
			if c.Definition.ID == "forward" {
				if len(c.Changes) != 2 {
					t.Fatal("lost tailoring path")
				}
				for _, change := range c.Changes {
					if change.Policy.ID == "" || change.Policy.Revision == "" || len(change.Policy.Sources) != 1 || change.Parent.Parent != "standard" {
						t.Fatal("missing change attribution", change)
					}
				}
				if i == 0 {
					expected = c.Changes
				} else if !equal(expected, c.Changes) {
					t.Fatal("nondeterministic deviation explanation")
				}
			}
		}
	}
	s = fixture(t)
	w := s.Sources[0].Waivers[0]
	s.Sources[0].Waivers = append(s.Sources[0].Waivers, w)
	_, r, _ := assess(t, s)
	if outcome(t, r, "C", "audit").Status != "WAIVED" {
		t.Fatal("exact duplicate did not coalesce")
	}
	s.Sources[0].Waivers[1].Start = "2026-10-01T00:00:00Z"
	s.Sources[0].Waivers[1].End = "2026-10-02T00:00:00Z"
	wantRefusal(t, s)
}
func TestReviewRetainedObservationAndObjectiveReferences(t *testing.T) {
	_, r, _ := assess(t, fixture(t))
	for i := range r.Results {
		if r.Results[i].Subject == "C" {
			for j := range r.Results[i].Outcomes {
				o := &r.Results[i].Outcomes[j]
				if o.Check == "forward" {
					o.Selected[0].ID = "S-forward"
					uses := []Use{}
					for _, u := range o.Candidates {
						if u.Candidate == "C-forward" {
							continue
						}
						if u.Candidate == "S-forward" {
							u.Reason = "qualified"
						}
						uses = append(uses, u)
					}
					o.Candidates = uses
				}
			}
		}
	}
	if ValidateRecord(r) == nil {
		t.Fatal("conflicting complete observation IDs admitted across results")
	}
	for _, mode := range []string{"foreign-objective", "missing-realization-id", "invalid-state", "contradictory-gap", "missing-determination-basis"} {
		t.Run(mode, func(t *testing.T) {
			_, r, _ := assess(t, fixture(t))
			o := &r.Plan.Subjects[0].Objectives[0]
			switch mode {
			case "foreign-objective":
				o.Realization.Objective = "foreign"
			case "missing-realization-id":
				o.Realization.ID = ""
			case "invalid-state":
				o.Realization.State = "invented"
				o.Gap = true
			case "contradictory-gap":
				o.Gap = true
			case "missing-determination-basis":
				o.Realization.State = "not-applicable"
				o.Realization.Checks = nil
			}
			if ValidateRecord(r) == nil {
				t.Fatal("invalid realization relationship accepted")
			}
		})
	}
}
