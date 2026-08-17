# Applying the mortgage cassette patch

One patch, on top of `origin/main` (703484e — same HEAD you already have).

## Apply

```bash
cd ~/path/to/sentinel_os
git checkout main
git am 0001-mortgage-cassette.patch
```

`git am` preserves the commit message as-is (it's long on purpose —
the "why" for the 3-year horizon and the resolution vocabulary is
worth having in `git log`, not just in this doc).

## Verify

```bash
pytest sentinel_os/Tests/test_mortgage_cassette.py -v   # 27 tests, all new
pytest sentinel_os/ -q                                   # full suite
```

Expect **629 passed, 6 skipped** (your last confirmed baseline was
584/6 — the extra 18 beyond the 27 new ones here are `test_twin_live.py`'s
real-infra suite, which needed a one-time `twin_ensure_services`
provisioning step on my end that may not be set up on your machine
yet; if you don't have `/usr/local/bin/twin_ensure_services` installed,
you'll see 611/6 instead, which is still clean).

## What's in the patch

- `sentinel_os/cassettes/mortgage_cassette.py` — the cassette itself.
  Read the module docstring first; it carries all the locked domain
  decisions (resolution vocabulary, the 3-year horizon and its
  research backing, the property-address field name) as the
  source-of-truth comment, not just chat history.
- `sentinel_os/Tests/test_mortgage_cassette.py` — 27 tests.

No existing files touched. This cassette auto-registers the moment
you drop it in `cassettes/` (the loader globs `*_cassette.py`), so no
wiring is needed elsewhere.

## Two things deliberately NOT in this patch

1. **Abandon-on-modification.** When a permanent loan modification
   issues a new loan number, the original obligation needs to move to
   ABANDONED under `REASON_DECISION_SUPERSEDED`, and a fresh
   decision+obligation opens under the new number. That's
   orchestration — the same layer `obligation_sweep.py` lives at, not
   cassette logic — and isn't built yet. `classify_outcome` is written
   so it's never handed a modification event to begin with.
2. **The ZIP/county regional-equity cohort dimension.** Reuses the
   BISG geocoder against `loan_property_address` once it exists — not
   part of this patch.

Both are called out again in the commit message and the module
docstring, so nothing here relies on remembering this file.
