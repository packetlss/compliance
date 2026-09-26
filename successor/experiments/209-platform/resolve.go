package experiment

import (
	"crypto/rand"
	"encoding/hex"
	"sort"
)

func newID() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b[:])
}
func insert[T any](m map[string]T, id string, v T) error {
	if id == "" {
		return fail("empty definition ID")
	}
	if old, ok := m[id]; ok && !equal(old, v) {
		return fail("divergent definition %s", id)
	}
	m[id] = v
	return nil
}

type catalog struct {
	checks        map[string]Check
	policies      map[string]Policy
	parameters    map[string]Parameter
	objectives    map[string]Objective
	realizations  map[string]Realization
	origins       map[string][]Attribution
	policyOrigins map[string][]Attribution
}

func Resolve(s Snapshot) (Plan, error) {
	if len(s.Sources) > 16 || len(s.Inventory.Subjects) > 16 || len(s.Evidence.Observations) > MaxItems {
		return Plan{}, fail("experiment collection limit")
	}
	p := Plan{ID: newID(), Operation: newID(), Slots: append([]string{}, s.Inventory.Selected...)}
	if len(p.Slots) == 0 || !unique(p.Slots) {
		return p, fail("invalid selected subjects")
	}
	sort.Strings(p.Slots)
	c := catalog{map[string]Check{}, map[string]Policy{}, map[string]Parameter{}, map[string]Objective{}, map[string]Realization{}, map[string][]Attribution{}, map[string][]Attribution{}}
	waivers := map[string]Waiver{}
	sources := map[string]Source{}
	for _, src := range s.Sources {
		if src.Revision == "" {
			return p, fail("source revision required")
		}
		if e := insert(sources, src.Name, src); e != nil {
			return p, e
		}
	}
	// Sort names for diagnostics only; definition/assignment conflicts have no winner.
	names := []string{}
	for name := range sources {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		src := sources[name]
		for _, w := range src.Waivers {
			if e := insert(waivers, w.ID, w); e != nil {
				return p, e
			}
		}
		for _, x := range src.Checks {
			if x.Revision == "" || x.Meaning == "" || x.Module == "" || len(x.Module) > 16384 || len(x.Schema) == 0 || !validType(x.ValueType) {
				return p, fail("invalid check %s", x.ID)
			}
			for _, t := range x.Schema {
				if !validType(t) {
					return p, fail("invalid schema")
				}
			}
			if e := insert(c.checks, x.ID, x); e != nil {
				return p, e
			}
			c.origins[x.ID] = append(c.origins[x.ID], Attribution{src.Name, src.Revision})
		}
		for _, x := range src.Policies {
			if x.Revision == "" {
				return p, fail("policy revision required")
			}
			if e := insert(c.policies, x.ID, x); e != nil {
				return p, e
			}
			c.policyOrigins[x.ID] = append(c.policyOrigins[x.ID], Attribution{src.Name, src.Revision})
		}
		for _, x := range src.Parameters {
			if x.Revision == "" {
				return p, fail("parameter revision required")
			}
			if e := insert(c.parameters, x.ID, x); e != nil {
				return p, e
			}
		}
		for _, x := range src.Objectives {
			if x.Meaning == "" || x.Baseline == "" {
				return p, fail("objective meaning/group required")
			}
			if e := insert(c.objectives, x.ID, x); e != nil {
				return p, e
			}
		}
		for _, x := range src.Realizations {
			if e := insert(c.realizations, x.ID, x); e != nil {
				return p, e
			}
		}
	}
	groups := map[string]Group{}
	for _, g := range s.Inventory.Groups {
		if e := insert(groups, g.ID, g); e != nil {
			return p, e
		}
	}
	subjects := map[string]Subject{}
	for _, sub := range s.Inventory.Subjects {
		if e := insert(subjects, sub.ID, sub); e != nil {
			return p, e
		}
	}
	for _, id := range p.Slots {
		sub, ok := subjects[id]
		if !ok {
			return p, fail("unknown selected subject %s", id)
		}
		active := map[string]bool{}
		var visit func(string, map[string]bool) error
		visit = func(id string, seen map[string]bool) error {
			if seen[id] {
				return fail("group cycle")
			}
			g, ok := groups[id]
			if !ok {
				return fail("missing group %s", id)
			}
			active[id] = true
			seen[id] = true
			for _, parent := range g.Parents {
				if e := visit(parent, seen); e != nil {
					return e
				}
			}
			delete(seen, id)
			return nil
		}
		// Validate all DAG edges, including currently inactive groups.
		for gid := range groups {
			if e := visit(gid, map[string]bool{}); e != nil {
				return p, e
			}
		}
		active = map[string]bool{}
		for gid, g := range groups {
			if contains(sub.Classes, g.Class) {
				if e := visit(gid, map[string]bool{}); e != nil {
					return p, e
				}
			}
		}
		ps, vs, oset, rs := map[string]bool{}, map[string]bool{}, map[string]bool{}, map[string]bool{}
		sp := SubjectPlan{Subject: id}
		for _, name := range names {
			src := sources[name]
			for _, a := range src.Assignments {
				if _, ok := groups[a.Group]; !ok {
					return p, fail("assignment group missing")
				}
				if active[a.Group] {
					for _, x := range a.Policies {
						ps[x] = true
					}
					for _, x := range a.Parameters {
						vs[x] = true
					}
					for _, x := range a.Objectives {
						oset[x] = true
					}
					for _, x := range a.Realizations {
						rs[x] = true
					}
				}
			}
		}
		for _, w := range waivers {
			start, e := stamp(w.Start)
			if e != nil {
				return p, e
			}
			end, e := stamp(w.End)
			if e != nil || !end.After(start) || w.Reason == "" || w.Approval == "" {
				return p, fail("invalid waiver")
			}
			if _, ok := subjects[w.Subject]; !ok {
				return p, fail("waiver subject missing")
			}
			if _, ok := c.checks[w.Check]; !ok {
				return p, fail("waiver check missing")
			}
			if w.Subject == id {
				sp.Waivers = append(sp.Waivers, w)
			}
		}
		vals := map[string]map[string]any{}
		for v := range vs {
			x, e := c.parameter(v, map[string]bool{})
			if e != nil {
				return p, e
			}
			vals[v] = x
		}
		sp.Parameters = vals
		for _, name := range names {
			src := sources[name]
			sp.Sources = append(sp.Sources, Attribution{src.Name, src.Revision})
		}
		for pid := range ps {
			selection := Selection{ID: pid, Revision: c.policies[pid].Revision}
			for _, name := range names {
				for _, pol := range sources[name].Policies {
					if pol.ID == pid {
						selection.Sources = append(selection.Sources, Attribution{name, sources[name].Revision})
					}
				}
			}
			sp.Policies = append(sp.Policies, selection)
		}
		sort.Slice(sp.Policies, func(i, j int) bool { return sp.Policies[i].ID < sp.Policies[j].ID })
		resolved := map[string]ResolvedCheck{}
		excluded := map[string]Exclusion{}
		add := func(rc ResolvedCheck) error {
			cid := rc.Definition.ID
			if _, ok := excluded[cid]; ok {
				return fail("excluded and required %s", cid)
			}
			if old, ok := resolved[cid]; ok {
				if !equal(old.Definition, rc.Definition) || !equal(old.Desired, rc.Desired) || old.FreshSeconds != rc.FreshSeconds {
					return fail("contradictory check %s", cid)
				}
				changes := map[string]AppliedChange{}
				for _, change := range append(append([]AppliedChange{}, old.Changes...), rc.Changes...) {
					if e := insert(changes, change.Policy.ID, change); e != nil {
						return e
					}
				}
				old.Changes = nil
				for _, change := range changes {
					old.Changes = append(old.Changes, change)
				}
				sort.Slice(old.Changes, func(i, j int) bool { return old.Changes[i].Policy.ID < old.Changes[j].Policy.ID })
				resolved[cid] = old
				return nil
			}
			resolved[cid] = rc
			return nil
		}
		for pid := range ps {
			checks, ex, e := c.policy(pid, vals, map[string]bool{})
			if e != nil {
				return p, e
			}
			for _, x := range ex {
				if _, ok := resolved[x.Check]; ok {
					return p, fail("excluded and required %s", x.Check)
				}
				if e := insert(excluded, x.Check, x); e != nil {
					return p, e
				}
			}
			for _, rc := range checks {
				if e := add(rc); e != nil {
					return p, e
				}
			}
		}
		for oid := range oset {
			o, ok := c.objectives[oid]
			if !ok {
				return p, fail("missing Objective")
			}
			matches := []Realization{}
			for rid := range rs {
				r, ok := c.realizations[rid]
				if !ok {
					return p, fail("missing realization")
				}
				if _, ok := c.objectives[r.Objective]; !ok {
					return p, fail("realization Objective missing")
				}
				if r.Objective == oid {
					matches = append(matches, r)
				}
			}
			if len(matches) > 1 {
				return p, fail("ambiguous realization %s", oid)
			}
			ro := ResolvedObjective{Definition: o, Gap: true}
			if len(matches) == 1 {
				r := matches[0]
				ro.Realization = r
				switch r.State {
				case "implemented":
					if len(r.Checks) == 0 || !unique(r.Checks) {
						return p, fail("invalid complete realization")
					}
					ro.Gap = false
					for _, cid := range r.Checks {
						rc, e := c.check(cid, vals)
						if e != nil {
							return p, e
						}
						if e = add(rc); e != nil {
							return p, e
						}
					}
				case "not-implemented", "not-applicable":
					if len(r.Checks) != 0 || r.Reason == "" || r.Approval == "" {
						return p, fail("invalid determination")
					}
					ro.Gap = r.State == "not-implemented"
				default:
					return p, fail("invalid realization state")
				}
			}
			sp.Objectives = append(sp.Objectives, ro)
		}
		for _, rc := range resolved {
			sort.Slice(rc.Changes, func(i, j int) bool { return rc.Changes[i].Policy.ID < rc.Changes[j].Policy.ID })
			sp.Checks = append(sp.Checks, rc)
		}
		for _, ex := range excluded {
			sp.Exclusions = append(sp.Exclusions, ex)
		}
		sp.CoverageGap = len(ps) == 0 && len(oset) == 0
		sort.Slice(sp.Checks, func(i, j int) bool { return sp.Checks[i].Definition.ID < sp.Checks[j].Definition.ID })
		sort.Slice(sp.Exclusions, func(i, j int) bool { return sp.Exclusions[i].Check < sp.Exclusions[j].Check })
		sort.Slice(sp.Objectives, func(i, j int) bool { return sp.Objectives[i].Definition.ID < sp.Objectives[j].Definition.ID })
		sort.Slice(sp.Waivers, func(i, j int) bool { return sp.Waivers[i].ID < sp.Waivers[j].ID })
		if len(sp.Checks) > 64 {
			return p, fail("experiment check limit")
		}
		p.Subjects = append(p.Subjects, sp)
	}
	return p, nil
}
func (c catalog) parameter(id string, seen map[string]bool) (map[string]any, error) {
	if seen[id] {
		return nil, fail("parameter cycle")
	}
	seen[id] = true
	defer delete(seen, id)
	v, ok := c.parameters[id]
	if !ok {
		return nil, fail("missing parameter %s", id)
	}
	out := map[string]any{}
	if v.Parent.Parent != "" {
		parent, ok := c.parameters[v.Parent.Parent]
		if !ok || parent.Revision != v.Parent.Revision {
			return nil, fail("stale parameter parent")
		}
		base, e := c.parameter(parent.ID, seen)
		if e != nil {
			return nil, e
		}
		for k, x := range base {
			out[k] = x
		}
		if len(v.Values) != len(v.Expected) {
			return nil, fail("expected parameter guards required")
		}
		for k, x := range v.Values {
			old, ok := out[k]
			want, guard := v.Expected[k]
			if !ok || !guard || !equal(old, want) {
				return nil, fail("stale parameter value %s", k)
			}
			out[k] = x
		}
	} else {
		if len(v.Expected) != 0 {
			return nil, fail("unexpected root guard")
		}
		for k, x := range v.Values {
			out[k] = x
		}
	}
	return out, nil
}
func linked(l Link, vals map[string]map[string]any) (any, error) {
	if l.Parameter == "" || l.Key == "" || !validType(l.Type) {
		return nil, fail("invalid consumer interface")
	}
	v, ok := vals[l.Parameter][l.Key]
	if !ok || !typed(v, l.Type) {
		return nil, fail("missing or invalid parameter consumer %s/%s", l.Parameter, l.Key)
	}
	return v, nil
}
func (c catalog) check(id string, vals map[string]map[string]any) (ResolvedCheck, error) {
	x, ok := c.checks[id]
	if !ok {
		return ResolvedCheck{}, fail("missing check %s", id)
	}
	desired := x.Desired
	if x.DesiredLink.Parameter != "" {
		if x.DesiredLink.Type != x.ValueType {
			return ResolvedCheck{}, fail("stale final interface")
		}
		var e error
		desired, e = linked(x.DesiredLink, vals)
		if e != nil {
			return ResolvedCheck{}, e
		}
	}
	if !typed(desired, x.ValueType) {
		return ResolvedCheck{}, fail("desired type %s", id)
	}
	v, e := linked(x.Freshness, vals)
	if e != nil {
		return ResolvedCheck{}, e
	}
	n, ok := integer(v)
	if !ok || n <= 0 || n > 86400*30 {
		return ResolvedCheck{}, fail("invalid freshness")
	}
	return ResolvedCheck{x, desired, n, c.origins[id], nil}, nil
}
func (c catalog) policy(id string, vals map[string]map[string]any, seen map[string]bool) (map[string]ResolvedCheck, []Exclusion, error) {
	if seen[id] {
		return nil, nil, fail("policy cycle")
	}
	seen[id] = true
	defer delete(seen, id)
	p, ok := c.policies[id]
	if !ok {
		return nil, nil, fail("missing policy %s", id)
	}
	checks := map[string]ResolvedCheck{}
	ex := []Exclusion{}
	if p.Parent.Parent != "" {
		parent, ok := c.policies[p.Parent.Parent]
		if !ok || parent.Revision != p.Parent.Revision {
			return nil, nil, fail("stale policy parent")
		}
		var e error
		checks, ex, e = c.policy(parent.ID, vals, seen)
		if e != nil {
			return nil, nil, e
		}
	}
	if !unique(p.Checks) {
		return nil, nil, fail("duplicate check")
	}
	for _, id := range p.Checks {
		if _, exists := checks[id]; exists {
			return nil, nil, fail("duplicate inherited check")
		}
		rc, e := c.check(id, vals)
		if e != nil {
			return nil, nil, e
		}
		checks[id] = rc
	}
	changed := map[string]bool{}
	for _, ch := range p.Changes {
		rc, ok := checks[ch.Check]
		if !ok || changed[ch.Check] || !equal(rc.Desired, ch.Expected) || !typed(ch.Value, rc.Definition.ValueType) || ch.Reason == "" || ch.Approval == "" {
			return nil, nil, fail("stale/invalid change %s", ch.Check)
		}
		changed[ch.Check] = true
		rc.Desired = ch.Value
		rc.Changes = append(rc.Changes, AppliedChange{ch, Selection{p.ID, p.Revision, c.policyOrigins[p.ID]}, p.Parent})
		checks[ch.Check] = rc
	}
	for _, x := range p.Exclusions {
		if _, ok := checks[x.Check]; !ok || x.Reason == "" || x.Approval == "" {
			return nil, nil, fail("invalid exclusion")
		}
		delete(checks, x.Check)
		ex = append(ex, x)
	}
	return checks, ex, nil
}
