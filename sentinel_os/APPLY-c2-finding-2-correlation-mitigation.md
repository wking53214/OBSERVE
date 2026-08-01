# C2 finding #2 mitigation: correlation-based proxy detection

Built and verified against your real repo (cloned fresh, origin/main
at `67eea1d` — confirmed this already includes the merged C2
dimension 4 / PR #6). Branch `c2-finding-2-correlation-mitigation`,
single commit `ae6559b` on top of `67eea1d`.

## What this does

Mitigates — does not fully close — the disclosed gap that renaming a
proxy variable to an innocuous name defeats the declared-name proxy
screen and the tier screen. New `check_correlation_based_proxy_detection`
in `regulatory_checks.py` screens input variable **values** instead of
**names**: for each numeric/boolean variable, it correlates the
variable's value against each group's estimated membership probability
(from the sealed channel) across a cohort. A rename alone no longer
helps, since the check never looks at the name.

**Deliberately narrow scope**, documented in the code, not hidden:
numeric/boolean variables only — string/categorical values aren't
screened this pass. **Not wired into the rollup or the shipped CFPB
lens this session** — that's a decision left open for you, same as
dimensions 2/3 sat unwired for a session before being wired in later.

## Files changed

- `regulatory_checks.py` — new `CohortInputDecision` dataclass, new
  `check_correlation_based_proxy_detection` function, module docstring
  updated (item 7), disclosed-limitations note updated.
- `regulatory_cassettes/README.md` — new check documented, out-of-scope
  note updated.
- `Tests/test_c2_correlation_based_proxy_detection.py` — new, 10 tests.

## Verification performed

- Full suite: **446 passed, 6 skipped** (the 6 are the BISG
  live-integration tests that skip cleanly without `CENSUS_API_KEY` —
  same as before this change), run **twice back-to-back with zero DB
  reset in between**, matching this repo's own verification standard.
- `ruff check .` — clean, using the CI-pinned `ruff==0.15.22`.
- `bandit -r . -x ./Tests -ll` — 0 High, 0 Medium.
- Manual sanity check before writing the test suite: planted a
  renamed proxy variable with a strong artificial correlation to a
  group and confirmed it's caught (`r≈0.999`) while an unrelated
  numeric variable and an unrelated boolean flag are correctly left
  clean.

## How to apply

From your local `sentinel_os` checkout (`origin/main` should already
be at `67eea1d` — the C2 dimension-4 merge):

```bash
git fetch /path/to/c2-finding-2-correlation-mitigation.bundle c2-finding-2-correlation-mitigation:c2-finding-2-correlation-mitigation
git checkout c2-finding-2-correlation-mitigation
```

Or, if you'd rather apply as a patch on top of your current branch:

```bash
git am c2-finding-2-correlation-mitigation.patch
```

Then run your usual full-suite check and merge to `main` whenever
you're satisfied.

## Still open (your call, not built this session)

1. **Whether to wire this into `rollup_c2_bias_identification` / the
   shipped CFPB lens.** Right now it's a standalone, fully tested
   checker. If you want it counted toward C2's PASS/FLAG/INDETERMINATE
   status, a caller needs to merge its findings into the
   `known_bad_variable_names` bucket alongside the existing proxy
   screen's — this wasn't done automatically so enabling it can't
   silently change anyone's existing rollup status.
2. **String/categorical variable values** — a renamed categorical
   proxy (e.g. a recoded neighborhood-cluster label) still isn't
   caught by anything. A real, disclosed gap.
3. **`CORRELATION_FLAG_THRESHOLD` (currently 0.5)** — a proposed
   starting point, not tuned against real data. Worth revisiting once
   this runs against something other than a synthetic cohort.
