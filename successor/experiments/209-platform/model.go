// Package experiment is disposable evidence for #209, not a production API.
package experiment

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"reflect"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

const MaxBytes = 1 << 20
const MaxItems = 128

type Subject struct {
	ID      string
	Classes []string
}
type Group struct {
	ID      string
	Class   string
	Parents []string
}
type Inventory struct {
	Subjects []Subject
	Groups   []Group
	Selected []string
}
type Guard struct {
	Parent   string
	Revision string
}
type Change struct {
	Check    string
	Expected any
	Value    any
	Reason   string
	Approval string
}
type Exclusion struct {
	Check    string
	Reason   string
	Approval string
}
type Policy struct {
	ID         string
	Revision   string
	Parent     Guard
	Checks     []string
	Changes    []Change
	Exclusions []Exclusion
}
type Parameter struct {
	ID       string
	Revision string
	Parent   Guard
	Values   map[string]any
	Expected map[string]any
}
type Link struct {
	Parameter string
	Key       string
	Type      string
}
type Check struct {
	ID          string
	Revision    string
	Meaning     string
	Module      string
	Schema      map[string]string
	Desired     any
	ValueType   string
	DesiredLink Link
	Freshness   Link
}
type Objective struct {
	ID       string
	Meaning  string
	Baseline string
}
type Realization struct {
	ID        string
	Objective string
	State     string
	Checks    []string
	Reason    string
	Approval  string
}
type Assignment struct {
	Group        string
	Policies     []string
	Parameters   []string
	Objectives   []string
	Realizations []string
}
type Waiver struct {
	ID       string
	Subject  string
	Check    string
	Start    string
	End      string
	Reason   string
	Approval string
}
type Source struct {
	Name         string
	Revision     string
	Policies     []Policy
	Parameters   []Parameter
	Checks       []Check
	Objectives   []Objective
	Realizations []Realization
	Assignments  []Assignment
	Waivers      []Waiver
}
type Observation struct {
	ID        string
	Subject   string
	Collector string
	At        string
	Facts     map[string]any
}
type Evidence struct{ Observations []Observation }

// Snapshot is operation-owned; callers must not mutate it while resolving/assessing.
type Snapshot struct {
	Inventory Inventory
	Sources   []Source
	Evidence  Evidence
}
type Attribution struct {
	Source   string
	Revision string
}
type ResolvedCheck struct {
	Definition   Check
	Desired      any
	FreshSeconds int64
	Attribution  []Attribution
	Changes      []Change
}
type ResolvedObjective struct {
	Definition  Objective
	Realization Realization
	Gap         bool
}
type Selection struct {
	ID       string
	Revision string
	Sources  []Attribution
}
type SubjectPlan struct {
	Policies    []Selection
	Parameters  map[string]map[string]any
	Sources     []Attribution
	Subject     string
	Checks      []ResolvedCheck
	Objectives  []ResolvedObjective
	Exclusions  []Exclusion
	Waivers     []Waiver
	CoverageGap bool
}
type Plan struct {
	ID        string
	Operation string
	Slots     []string
	Subjects  []SubjectPlan
}
type Use struct {
	Candidate string
	Reason    string
}
type Outcome struct {
	Check      string
	Status     string
	Underlying string
	Waiver     *Waiver
	Diagnostic string
	Candidates []Use
	Selected   []Observation
}
type Result struct {
	ID        string
	Operation string
	Plan      string
	Subject   string
	At        string
	Outcomes  []Outcome
}
type Record struct {
	Version   string
	Operation string
	Plan      Plan
	Results   []Result
}
type Summary struct {
	Subjects   int
	Missing    []string
	Status     string
	Objectives map[string]string
	Record     Record
}

func fail(format string, args ...any) error { return fmt.Errorf(format, args...) }
func equal(a, b any) bool                   { return reflect.DeepEqual(a, b) }
func contains(xs []string, s string) bool {
	for _, x := range xs {
		if x == s {
			return true
		}
	}
	return false
}
func unique(xs []string) bool {
	m := map[string]bool{}
	for _, x := range xs {
		if x == "" || m[x] {
			return false
		}
		m[x] = true
	}
	return true
}
func stamp(s string) (time.Time, error) {
	t, e := time.Parse("2006-01-02T15:04:05Z", s)
	if e != nil || t.Format("2006-01-02T15:04:05Z") != s {
		return t, fail("invalid UTC timestamp %q", s)
	}
	return t, nil
}
func integer(v any) (int64, bool) {
	n, ok := v.(json.Number)
	if !ok {
		return 0, false
	}
	i, e := strconv.ParseInt(string(n), 10, 64)
	return i, e == nil && i >= -9007199254740991 && i <= 9007199254740991
}
func typed(v any, t string) bool {
	switch t {
	case "integer":
		_, ok := integer(v)
		return ok
	case "boolean":
		_, ok := v.(bool)
		return ok
	case "string":
		_, ok := v.(string)
		return ok
	case "strings":
		a, ok := v.([]any)
		if !ok {
			return false
		}
		for _, x := range a {
			if _, ok := x.(string); !ok {
				return false
			}
		}
		return true
	}
	return false
}
func validType(t string) bool {
	return contains([]string{"integer", "boolean", "string", "strings"}, t)
}

// Scan first: encoding/json otherwise accepts duplicate members and case-insensitive
// field aliases. Every object key is checked; struct decoding also checks exact keys.
func scan(d *json.Decoder, depth int) (any, error) {
	if depth > 32 {
		return nil, fail("JSON nesting limit")
	}
	t, e := d.Token()
	if e != nil {
		return nil, e
	}
	switch v := t.(type) {
	case json.Delim:
		switch v {
		case '{':
			m := map[string]any{}
			for d.More() {
				k, e := d.Token()
				if e != nil {
					return nil, e
				}
				s, ok := k.(string)
				if !ok {
					return nil, fail("object key")
				}
				if _, ok = m[s]; ok {
					return nil, fail("duplicate member %s", s)
				}
				x, e := scan(d, depth+1)
				if e != nil {
					return nil, e
				}
				m[s] = x
				if len(m) > MaxItems {
					return nil, fail("object limit")
				}
			}
			_, e = d.Token()
			return m, e
		case '[':
			a := []any{}
			for d.More() {
				x, e := scan(d, depth+1)
				if e != nil {
					return nil, e
				}
				a = append(a, x)
				if len(a) > MaxItems {
					return nil, fail("array limit")
				}
			}
			_, e = d.Token()
			return a, e
		}
		return nil, fail("delimiter")
	case json.Number:
		if string(v) == "-0" || strings.ContainsAny(string(v), ".eE") {
			return nil, fail("only integer numbers supported")
		}
		if _, ok := integer(v); !ok {
			return nil, fail("number range")
		}
		return v, nil
	case nil:
		return nil, fail("null is not supported")
	default:
		return t, nil
	}
}
func exactKeys(v any, t reflect.Type) error {
	if t.Kind() == reflect.Pointer {
		return exactKeys(v, t.Elem())
	}
	switch t.Kind() {
	case reflect.Struct:
		m, ok := v.(map[string]any)
		if !ok {
			return fail("expected object")
		}
		for k, x := range m {
			f, ok := t.FieldByName(k)
			if !ok {
				return fail("unknown member %s", k)
			}
			if e := exactKeys(x, f.Type); e != nil {
				return e
			}
		}
	case reflect.Slice:
		a, ok := v.([]any)
		if !ok {
			return fail("expected array")
		}
		for _, x := range a {
			if e := exactKeys(x, t.Elem()); e != nil {
				return e
			}
		}
	case reflect.Map:
		m, ok := v.(map[string]any)
		if !ok {
			return fail("expected map")
		}
		for _, x := range m {
			if e := exactKeys(x, t.Elem()); e != nil {
				return e
			}
		}
	}
	return nil
}
func Decode(b []byte, out any) error {
	if len(b) > MaxBytes || !utf8.Valid(b) || !unicodeEscapes(b) {
		return fail("input size/UTF-8")
	}
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	v, e := scan(d, 0)
	if e != nil {
		return e
	}
	if _, e = d.Token(); e != io.EOF {
		return fail("trailing JSON")
	}
	if e = exactKeys(v, reflect.TypeOf(out)); e != nil {
		return e
	}
	d = json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	d.DisallowUnknownFields()
	return d.Decode(out)
}

// Omit absent fields/nulls in retained output so the same strict subset can read it.
func Encode(v any) ([]byte, error) {
	b, e := json.Marshal(v)
	if e != nil {
		return nil, e
	}
	var raw any
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	if e = d.Decode(&raw); e != nil {
		return nil, e
	}
	var clean func(any) any
	clean = func(x any) any {
		switch y := x.(type) {
		case map[string]any:
			for k, z := range y {
				if z == nil {
					delete(y, k)
				} else {
					y[k] = clean(z)
				}
			}
		case []any:
			for i, z := range y {
				y[i] = clean(z)
			}
		}
		return x
	}
	return json.MarshalIndent(clean(raw), "", "  ")
}

// encoding/json replaces lone escaped surrogates; reject them before decoding so
// two distinct authored strings cannot silently become the same replacement rune.
func unicodeEscapes(b []byte) bool {
	for i := 0; i < len(b); i++ {
		if b[i] != '\\' {
			continue
		}
		i++
		if i >= len(b) {
			return false
		}
		if b[i] != 'u' {
			continue
		}
		if i+4 >= len(b) {
			return false
		}
		n, e := strconv.ParseUint(string(b[i+1:i+5]), 16, 16)
		if e != nil {
			return false
		}
		i += 4
		if n >= 0xdc00 && n <= 0xdfff {
			return false
		}
		if n >= 0xd800 && n <= 0xdbff {
			if i+6 >= len(b) || b[i+1] != '\\' || b[i+2] != 'u' {
				return false
			}
			low, e := strconv.ParseUint(string(b[i+3:i+7]), 16, 16)
			if e != nil || low < 0xdc00 || low > 0xdfff {
				return false
			}
			i += 6
		}
	}
	return true
}
