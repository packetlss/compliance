# Disposable #209 Phase B assumptions (not production contracts)

Target: successor. Verified starting base: fa49127ec30675a47486dd9f5d1e1485e4032fd4
(Phase A #215). Authority: #209 and its current comments, ADR 0025 and the target's
SUCCESSOR_ARCHITECTURE.md. No production promotion is implied by these probes.

Written before implementation. Alternative designs and provisional choices:

1. **Stable input admission:** try an operator-controlled local acquisition directory,
   with one persistent advisory lock inode covering inventory, independently named
   source files (including inline modules and observation interfaces), and evidence.
   All writers must acquire the exclusive lock before changing any constituent;
   admission holds a shared nonblocking lock across the whole read, then owns copies.
   External acquisition must finish coherently before releasing its exclusive lock.
   Do not replace the lock inode, use symlinks, or use a filesystem without reliable
   advisory locking. Refuse contention, unsupported files and oversized input.
   Probe writer contention and changes after loading. This is cooperative isolation,
   NOT a defense against noncooperating writers or hostile filesystem substitution.
   Alternatives: externally frozen filesystem snapshot/read-only volume or one
   atomically published envelope with a trusted immutable-writer discipline. Neither
   copying nor repeated hashing can prove a coherent concurrently changing directory.
2. **Retained evidence:** inline complete selected synthetic observations plus
   candidate IDs and qualification diagnostics; preserve exact observation ID, subject,
   collector, timestamp and typed facts. An external frozen evidence-record design
   would reduce result duplication but creates another required retention dependency.
   Inline data exposes all selected facts to record readers; production must review
   minimization/access control. Missing retained facts must fail admission, never be
   repaired from current inputs. No history database or implicit discovery.
3. **Records:** random ordinary operation and plan IDs; explicit subject slots; one
   result per slot with exact child membership, references and assessment instant.
   A retained document owns the operation/plan and supplied results. Missing slots
   remain visible. Reject conflicting duplicates and foreign references. Publish an
   immutable-by-protocol file through a synced temporary file and exclusive hard link;
   never overwrite an existing name. Exact-byte retries may succeed, differing retries
   fail. Interruption before linking leaves no public record; after linking leaves a
   complete record. Filesystem durability and faithful external retention are trusted;
   IDs and structural checks cannot detect coordinated consistent rewriting.
4. **Typed authoring:** JSON only, duplicate/unknown members rejected, UTF-8, no null,
   integer numbers limited to +/- (2^53-1), no fractional/exponent numbers, booleans
   distinct from integers, ordered arrays, exact strings without normalization.
   RFC3339 UTC whole-second timestamps only. Explicit parent revision and expected
   typed inherited value guards, complete replacement values, exact final interfaces.
   No JCS, digests or content identities. Alternatives include exact decimals and
   YAML with explicitly specified duplicate/tag/alias rules; defer their added cost.

Go/embedded OPA versus clean Python/process design: Go offers one native executable
and direct cancellation without an installed interpreter or evaluator executable.
Python plus a subprocess would improve kill/memory/fault isolation but adds two
runtime deliveries and IPC interpretation. First measure Go's bounded trusted-policy
slice. No executable comparator is justified merely to compare language syntax;
reconsider if containment/deployment evidence leaves a material platform uncertainty.

Evaluator experiment: narrow allowlisted deterministic builtins; no SDK, remote OPA,
HTTP/DNS/time/random builtins, bundles or plugins. Limit input/module size, input
collection counts and per-evaluation wall time. In-process deadlines are cooperative,
not a hard memory/CPU sandbox. Do not claim hostile-policy isolation. Application
owns resolution, observation qualification, outcomes/waivers, records/publication.
