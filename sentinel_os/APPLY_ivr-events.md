# Applying the ivr_events ingestion contract

Base commit: `68cadfb` (your current `origin/main` — the mortgage cassette push).
One patch, one commit.

## Apply

```
cd ~/sentinel_os
git checkout main
git am ivr-events-patches/0001-Generic-ivr_events-ingestion-contract-real-per-node-.patch
```

If `git am` complains about a missing identity, that's your own git config,
not the patch — `git config user.name "..."` / `git config user.email "..."`.

## Verify

```
python -m pytest . --ignore=test_twin_live.py -v --tb=short
```

Expect **630 passed, 6 skipped** (611 baseline + 19 new). Verified twice
back-to-back in two independent clones before delivery, ruff (0.15.22) and
bandit -ll clean on every touched file.

Neither `twilio_log_ingestion.py` nor `production_harness.py` is in
`cassette_forensics._GOVERNANCE_CODE_MODULES`, so this does **not** bump any
cassette's code hash or version — no `ledger_entries` drop needed, unlike the
EventV1/OutcomeV1 and mortgage cassette patches.

## What this does, in one paragraph

Nothing changes for a plain Twilio call record — the phone-digit route guess
and the 0.1/0.5/0.4 wait split still run exactly as before, still stamped
ESTIMATED. New: if a Twilio record carries an `ivr_events` list — real
per-node data shaped `{"node": str, "wait_seconds": float, "source": str}` —
`parse_call_log` uses it directly and the resulting route/wait events are
stamped VERIFIED, naming the real source. Absent `ivr_events` entirely:
unchanged. Present but malformed (missing field, negative wait, empty list):
raises `ValueError` rather than quietly falling back to a guess. No specific
telephony vendor (Studio, TaskRouter, custom webhooks) is wired up — that's
a separate, later integration decision; this patch only builds the contract
whatever real source eventually plugs into.

## Left open

- No real event source is wired in yet — `ivr_events` has to be populated by
  whatever ingest layer eventually calls `parse_call_log` with real data.
- Downstream node-naming coupling (queue detection by `"queue"` substring,
  agent/resolution detection by literal `agent_a`/`agent_b`/etc. names) is
  unchanged and documented as a limitation in `twilio_log_ingestion.py`'s
  module docstring — a real event source's node names still need to follow
  that convention.
- `TwilioStreamAdapter.fetch_recent_calls` is still the placeholder stub
  (`return []`) — deliberately out of scope per your call on scoping this
  session.
