package experiment

import (
	"bytes"
	"os"
	"path/filepath"
	"sort"
)

func validatePlan(p Plan) error {
	if p.ID == "" || p.Operation == "" || len(p.Slots) == 0 || !unique(p.Slots) || len(p.Subjects) != len(p.Slots) {
		return fail("invalid plan membership")
	}
	seen := map[string]bool{}
	for _, sp := range p.Subjects {
		if !contains(p.Slots, sp.Subject) || seen[sp.Subject] {
			return fail("plan subject membership")
		}
		seen[sp.Subject] = true
		checks := map[string]bool{}
		for _, c := range sp.Checks {
			if checks[c.Definition.ID] || c.Definition.ID == "" || !typed(c.Desired, c.Definition.ValueType) || c.FreshSeconds <= 0 || c.Definition.Meaning == "" || len(c.Attribution) == 0 {
				return fail("invalid retained check")
			}
			checks[c.Definition.ID] = true
		}
		objs := map[string]bool{}
		for _, o := range sp.Objectives {
			if o.Definition.ID == "" || objs[o.Definition.ID] {
				return fail("Objective membership")
			}
			objs[o.Definition.ID] = true
			if o.Realization.State == "implemented" {
				if o.Gap || len(o.Realization.Checks) == 0 || !unique(o.Realization.Checks) {
					return fail("invalid retained realization")
				}
				for _, id := range o.Realization.Checks {
					if !checks[id] {
						return fail("missing realization check")
					}
				}
			} else if !o.Gap && o.Realization.State != "not-applicable" {
				return fail("invalid gap")
			}
		}
		for _, x := range sp.Exclusions {
			if checks[x.Check] || x.Reason == "" || x.Approval == "" {
				return fail("invalid retained exclusion")
			}
		}
	}
	return nil
}
func ValidateRecord(r Record) error {
	if r.Version != "experiment209-1" || r.Operation != r.Plan.Operation {
		return fail("record operation reference")
	}
	if e := validatePlan(r.Plan); e != nil {
		return e
	}
	plans := map[string]SubjectPlan{}
	for _, p := range r.Plan.Subjects {
		plans[p.Subject] = p
	}
	ids := map[string]Result{}
	slots := map[string]Result{}
	for _, result := range r.Results {
		if result.Operation != r.Operation || result.Plan != r.Plan.ID {
			return fail("foreign result reference")
		}
		sp, ok := plans[result.Subject]
		if !ok {
			return fail("wrong subject")
		}
		if e := insert(ids, result.ID, result); e != nil {
			return e
		}
		if e := insert(slots, result.Subject, result); e != nil {
			return e
		}
		at, e := stamp(result.At)
		if e != nil {
			return e
		}
		if len(result.Outcomes) != len(sp.Checks) {
			return fail("result child membership")
		}
		outcomes := map[string]Outcome{}
		for _, out := range result.Outcomes {
			if _, ok := outcomes[out.Check]; ok {
				return fail("duplicate child")
			}
			outcomes[out.Check] = out
		}
		for _, rc := range sp.Checks {
			out, ok := outcomes[rc.Definition.ID]
			if !ok {
				return fail("missing/unexpected child")
			}
			if !contains([]string{"PASS", "FAIL", "UNKNOWN", "ERROR", "WAIVED"}, out.Status) || out.Diagnostic == "" {
				return fail("invalid result outcome")
			}
			if out.Status == "WAIVED" {
				if out.Underlying != "FAIL" || out.Waiver == nil {
					return fail("missing waiver basis")
				}
				found := false
				for _, w := range sp.Waivers {
					if equal(w, *out.Waiver) {
						start, _ := stamp(w.Start)
						end, _ := stamp(w.End)
						found = w.Subject == sp.Subject && w.Check == out.Check && !at.Before(start) && at.Before(end)
					}
				}
				if !found {
					return fail("waiver not in plan/window")
				}
			} else if out.Waiver != nil || out.Underlying != "" {
				return fail("unexpected waiver")
			}
			if out.Status != "UNKNOWN" && len(out.Selected) == 0 {
				return fail("missing retained observation")
			}
			selected := map[string]Observation{}
			uses := map[string]string{}
			for _, u := range out.Candidates {
				if u.Candidate == "" || u.Reason == "" {
					return fail("invalid evidence use")
				}
				if _, ok := uses[u.Candidate]; ok {
					return fail("duplicate evidence use")
				}
				uses[u.Candidate] = u.Reason
			}
			for _, obs := range out.Selected {
				if qualifies(obs, sp.Subject, rc, at) != "qualified" || uses[obs.ID] != "qualified" {
					return fail("mismatched retained observation")
				}
				if e := insert(selected, obs.ID, obs); e != nil {
					return e
				}
			}
			if len(out.Selected) > 1 {
				first := out.Selected[0]
				first.ID = ""
				for _, obs := range out.Selected[1:] {
					obs.ID = ""
					if !equal(first, obs) {
						return fail("conflicting retained observations")
					}
				}
			}
		}
	}
	return nil
}

// Explain uses only supplied records. It never invokes resolution or the evaluator.
func Explain(r Record) (Summary, error) {
	s := Summary{Record: r, Subjects: len(r.Plan.Slots), Objectives: map[string]string{}}
	if e := ValidateRecord(r); e != nil {
		return s, e
	}
	results := map[string]Result{}
	for _, r := range r.Results {
		results[r.Subject] = r
	}
	overall := []string{}
	for _, sp := range r.Plan.Subjects {
		r, ok := results[sp.Subject]
		if !ok {
			s.Missing = append(s.Missing, sp.Subject)
			overall = append(overall, "UNKNOWN")
			continue
		}
		out := map[string]string{}
		for _, o := range r.Outcomes {
			out[o.Check] = o.Status
			overall = append(overall, o.Status)
		}
		if sp.CoverageGap {
			overall = append(overall, "UNKNOWN")
		}
		for _, o := range sp.Objectives {
			status := "UNKNOWN"
			if o.Realization.State == "not-applicable" {
				status = "NOT_APPLICABLE"
			} else if !o.Gap {
				xs := []string{}
				for _, id := range o.Realization.Checks {
					xs = append(xs, out[id])
				}
				status = rollup(xs)
			}
			s.Objectives[sp.Subject+"/"+o.Definition.ID] = status
			if status != "NOT_APPLICABLE" {
				overall = append(overall, status)
			}
		}
	}
	s.Status = rollup(overall)
	sort.Strings(s.Missing)
	return s, nil
}
func rollup(xs []string) string {
	if len(xs) == 0 {
		return "UNKNOWN"
	}
	for _, status := range []string{"FAIL", "ERROR", "UNKNOWN", "WAIVED"} {
		if contains(xs, status) {
			return status
		}
	}
	for _, x := range xs {
		if x != "PASS" {
			return "UNKNOWN"
		}
	}
	return "PASS"
}
func ReadRecord(path string) (Record, error) {
	var r Record
	b, e := boundedRead(path)
	if e != nil {
		return r, e
	}
	if e = Decode(b, &r); e != nil {
		return r, e
	}
	return r, ValidateRecord(r)
}
func Publish(path string, r Record) error { return publish(path, r, nil) }
func publish(path string, r Record, hook func() error) error {
	if e := ValidateRecord(r); e != nil {
		return e
	}
	b, e := Encode(r)
	if e != nil {
		return e
	}
	if len(b) > MaxBytes {
		return fail("record size limit")
	}
	dir := filepath.Dir(path)
	f, e := os.CreateTemp(dir, ".209-pending-*")
	if e != nil {
		return e
	}
	defer os.Remove(f.Name())
	defer f.Close()
	if e = f.Chmod(0600); e != nil {
		return e
	}
	if _, e = f.Write(b); e != nil {
		return e
	}
	if e = f.Sync(); e != nil {
		return e
	}
	if e = f.Close(); e != nil {
		return e
	}
	if hook != nil {
		if e = hook(); e != nil {
			return e
		}
	}
	if e = os.Link(f.Name(), path); e != nil {
		old, readErr := boundedRead(path)
		if readErr == nil && bytes.Equal(old, b) {
			return nil
		}
		return fail("publication refuses existing/different destination: %w", e)
	}
	d, e := os.Open(dir)
	if e != nil {
		return e
	}
	defer d.Close()
	return d.Sync()
}
