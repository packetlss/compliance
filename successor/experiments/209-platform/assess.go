package experiment

import (
	"context"
	"sort"
	"time"

	"github.com/open-policy-agent/opa/v1/ast"
	"github.com/open-policy-agent/opa/v1/rego"
)

// Positive allowlist: adding new OPA builtins cannot silently widen this boundary.
func capabilities() *ast.Capabilities {
	caps := ast.CapabilitiesForThisVersion()
	allowed := []string{"eq", "equal", "neq", "gt", "gte", "lt", "lte", "count", "plus", "minus", "mul", "div", "internal.member_2", "internal.member_3"}
	filtered := []*ast.Builtin{}
	for _, b := range caps.Builtins {
		if contains(allowed, b.Name) {
			filtered = append(filtered, b)
		}
	}
	caps.Builtins = filtered
	caps.AllowNet = []string{}
	return caps
}
func Evaluate(ctx context.Context, module string, input any) (string, string) {
	if len(module) > 16384 {
		return "ERROR", "module size limit"
	}
	if e := ctx.Err(); e != nil {
		return "ERROR", "criterion cancelled"
	}
	ctx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
	defer cancel()
	q, e := rego.New(rego.Query("data.criterion.decision"), rego.Module("admitted.rego", module), rego.Capabilities(capabilities()), rego.StrictBuiltinErrors(true)).PrepareForEval(ctx)
	if e != nil {
		return "ERROR", "criterion compile/capability error"
	}
	rs, e := q.Eval(ctx, rego.EvalInput(input))
	if e != nil {
		return "ERROR", "criterion execution/cancellation error"
	}
	if len(rs) != 1 || len(rs[0].Expressions) != 1 {
		return "ERROR", "missing or multiple decisions"
	}
	obj, ok := rs[0].Expressions[0].Value.(map[string]any)
	if !ok || len(obj) != 2 {
		return "ERROR", "malformed decision"
	}
	s, ok := obj["satisfied"].(bool)
	c, ok2 := obj["conclusive"].(bool)
	if !ok || !ok2 {
		return "ERROR", "malformed decision"
	}
	if !c {
		return "UNKNOWN", "criterion inconclusive"
	}
	if s {
		return "PASS", "criterion satisfied"
	}
	return "FAIL", "criterion not satisfied"
}
func qualifies(o Observation, subject string, rc ResolvedCheck, at time.Time) string {
	if o.Subject != subject {
		return "other subject"
	}
	if o.ID == "" || o.Collector == "" {
		return "missing observation identity"
	}
	t, e := stamp(o.At)
	if e != nil {
		return "invalid observation time"
	}
	if t.After(at) {
		return "future observation"
	}
	if at.Sub(t) > time.Duration(rc.FreshSeconds)*time.Second {
		return "stale observation"
	}
	if len(o.Facts) != len(rc.Definition.Schema) {
		return "schema invalid"
	}
	for k, typ := range rc.Definition.Schema {
		if !typed(o.Facts[k], typ) {
			return "schema invalid: field " + k + " expects " + typ
		}
	}
	return "qualified"
}
func Assess(ctx context.Context, p Plan, evidence Evidence, atText string) (Record, error) {
	r := Record{Version: "experiment209-1", Operation: p.Operation, Plan: p}
	at, e := stamp(atText)
	if e != nil {
		return r, e
	}
	if e = validatePlan(p); e != nil {
		return r, e
	}
	if ctx.Err() != nil {
		return r, fail("shared prerequisite: cancelled before assessment")
	}
	// Duplicate IDs must identify complete identical observations, never choose order.
	obs := map[string]Observation{}
	for _, o := range evidence.Observations {
		if o.ID == "" {
			return r, fail("shared prerequisite: observation ID missing")
		}
		if e := insert(obs, o.ID, o); e != nil {
			return r, fail("shared prerequisite: %w", e)
		}
	}
	ids := []string{}
	for id := range obs {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, sp := range p.Subjects {
		result := Result{ID: newID(), Operation: p.Operation, Plan: p.ID, Subject: sp.Subject, At: atText}
		for _, rc := range sp.Checks {
			out := Outcome{Check: rc.Definition.ID, Status: "UNKNOWN", Diagnostic: "no qualified observation"}
			candidates := []Observation{}
			for _, id := range ids {
				o := obs[id]
				reason := qualifies(o, sp.Subject, rc, at)
				out.Candidates = append(out.Candidates, Use{id, reason})
				if reason == "qualified" {
					candidates = append(candidates, o)
				}
			}
			if len(candidates) > 0 {
				same := true
				first := candidates[0]
				for _, o := range candidates[1:] { // IDs identify observations; complete duplicates require identical attribution, time, facts.
					a, b := first, o
					a.ID = ""
					b.ID = ""
					if !equal(a, b) {
						same = false
					}
				}
				if !same {
					out.Diagnostic = "ambiguous qualified observations"
				} else {
					out.Selected = candidates
					out.Status, out.Diagnostic = Evaluate(ctx, rc.Definition.Module, map[string]any{"observed": first.Facts, "desired": rc.Desired})
					if out.Status == "FAIL" {
						for _, w := range sp.Waivers {
							start, _ := stamp(w.Start)
							end, _ := stamp(w.End)
							if w.Check == out.Check && !at.Before(start) && at.Before(end) {
								if out.Waiver != nil {
									return r, fail("shared prerequisite: ambiguous waiver")
								}
								copy := w
								out.Waiver = &copy
								out.Underlying = "FAIL"
								out.Status = "WAIVED"
							}
						}
					}
				}
			}
			result.Outcomes = append(result.Outcomes, out)
		}
		r.Results = append(r.Results, result)
	}
	if e = ValidateRecord(r); e != nil {
		return Record{}, e
	}
	return r, nil
}
