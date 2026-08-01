# Wire correlation-based proxy detection into C2 rollup

Built and verified on your Chromebook using a fresh pull from origin/main
at baa6a19. Branch `wire-correlation-proxy-into-rollup`, single commit
`5c61e64`.

## What this does

The correlation-based proxy detection (check_correlation_based_proxy_detection)
was built July 24 and delivered via `c2-finding-2-correlation-mitigation`
bundle — it works, but wasn't wired into the C2 rollup scoring yet, so
CFPBRegBLens.c2_rollup() didn't use it. This makes it live as dimension 5.

When you call c2_rollup() and pass `correlation_proxy_findings=[]` (for
clean) or `correlation_proxy_findings=[<findings>]` (for flagged), the
dimension is included in the AND-rollup logic. Passing None (default) keeps
it INDETERMINATE, same as dimension 4. Pattern is identical to how you
already use statistical_outcome_equity_findings.

The correlation check still runs only when you run it explicitly on a cohort
(it's not called automatically from anywhere) — this just means its findings,
when you have them, feed into the overall C2 score instead of sitting separate.

## Files changed

- `regulatory_checks.py` — new DIMENSION_CORRELATION_PROXY_SIGNAL constant
- `regulatory_cassettes/cfpb_reg_b.py` — c2_rollup() now accepts
  correlation_proxy_findings parameter, wired into dimension_findings dict,
  module docstring and disclosed limitations updated
- `Tests/test_regulatory_cassettes.py` — 4 new c2_rollup tests (empty
  findings -> PASS, flagged findings -> FLAG, None -> INDETERMINATE, can
  flag alongside proxy screen), fixed 2 existing tests that check dimension
  counts
- `Tests/test_c2_statistical_outcome_equity.py` — fixed 2 tests that were
  calling c2_rollup() without the new optional parameter

## Verification performed

- Full suite: **456 passed, 6 skipped** (452 baseline from both earlier
  bundles + 4 new c2_rollup tests), run **twice back-to-back with zero DB
  reset in between**.
- `ruff check .` — clean (`ruff==0.15.22`).
- `bandit -r . -x ./Tests -ll` — 0 High, 0 Medium.

## How to apply

From your local sentinel_os checkout at baa6a19:

```bash
git fetch /path/to/wire-correlation-proxy-into-rollup.bundle \
  wire-correlation-proxy-into-rollup:wire-correlation-proxy-into-rollup
git checkout wire-correlation-proxy-into-rollup
python3 -m pytest . -q  # optional but recommended
git checkout main
git merge --ff-only wire-correlation-proxy-into-rollup
git push origin main
```

Or as a patch on your current branch:

```bash
git am wire-correlation-proxy-into-rollup.patch
git push origin main
```

This is a clean fast-forward merge onto baa6a19 (the final commit from the
earlier bundles) — no merge conflicts possible.

## Nothing left open

This was the only remaining open decision: whether to wire the correlation
check into the rollup or leave it standalone. Now wired and delivered.
Nothing else is known-outstanding on sentinel_os as of this commit.
