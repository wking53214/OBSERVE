# Engine re-sync: scoring differences (2026-11-19; totals re-measured 2026-11-23)

> **2026-11-23:** after re-syncing to observe-perceive `8d70b95` (new evidence-based limits, "child" group split), the corpus gives 240 field differences against the old engine ({'risk': 178, 'regime': 45, 'esc': 17}) and 13 readings that are less cautious ([47, 61, 131, 138, 143, 270, 271, 275, 284, 372, 577, 585, 592]) and 40 more cautious. The tables below are the 2026-11-19 measurement and are superseded; see `ENGINE_RESYNC_DISPOSITIONS.md` for the current less-cautious list. Needs clinical review.

OBSERVE's root engine was re-synced from observe-perceive `d596262` (see `VENDORED.md`). This lists how the engine in force now differs from the old OBSERVE engine on the recorded 600-reading corpus (`testdata/old_engine_corpus_20261029.json`, seed 20261029), with the one junk `previous_o2` input difference removed so only scoring is compared.

**This needs a clinical reviewer before merge.** Nothing here is a clinical validation. Reading numbers are positions in the corpus.

Totals: 50 readings differ in regime or escalation. 43 are more cautious (higher regime or a new escalation). 7 are less cautious (lower regime, or an escalation that no longer goes out).

The likely cause of the escalation drops: upstream's escalation lock now suppresses a repeat at the same severity, and lets a severity increase through (see the changed `test_escalation_lock_prevents_immediate_re_escalation`). That is an inference from the test and the readings, not confirmed line by line.

## Less cautious (review first)

| Reading | Patient | HR | SpO2 | RR | Temp C | Context | Old | New |
|---|---|---|---|---|---|---|---|---|
| 148 | P6 | 144 | 84.4 | 38 | 40.0 | {'age_months': 1} | critical, escalate True | critical, escalate False |
| 330 | P0 | 91 | nan | 25 | 38.3 | {'age_months': None} | warning, escalate True | critical, escalate False (unassessable) |
| 353 | P11 | 146 | 86.2 | 36 | 38.8 | {'age_months': None} | critical, escalate True | critical, escalate False |
| 378 | P11 | 84 | 93.2 | 28 | 36.5 | {'age_months': 48} | critical, escalate False | stable, escalate False |
| 398 | P11 | 148 | 93.2 | 21 | 36.7 | {'age_months': 48, 'force_heavy': True} | critical, escalate False | stable, escalate False |
| 481 | P7 | 174 | 88.8 | 43 | 39.4 | {'age_months': 18} | critical, escalate True | critical, escalate False |
| 585 | P10 | 84 | 250.0 | 39 | 38.1 | {'age_months': 1} | warning, escalate True | warning, escalate False (unassessable) |

## More cautious

| Reading | Patient | HR | SpO2 | RR | Temp C | Context | Old | New |
|---|---|---|---|---|---|---|---|---|
| 16 | P0 | 141 | 91.1 | 42 | 39.2 | {'age_months': 6} | warning, escalate False | critical, escalate False |
| 19 | P0 | 143 | 90.8 | 18 | 39.2 | {'age_months': 1} | warning, escalate False | critical, escalate False |
| 57 | P9 | 160 | 87.4 | 51 | 39.8 | {'age_months': 18, 'force_heavy': True} | critical, escalate False | critical, escalate True |
| 80 | P11 | 185 | 78.9 | 51 | 38.7 | {'age_months': 6, 'force_heavy': True} | critical, escalate False | critical, escalate True |
| 91 | P2 | 135 | 79.7 | 44 | 39.8 | {'age_months': None} | stable, escalate False | warning, escalate True |
| 106 | P0 | 145 | 90.9 | 40 | 39.3 | {'age_months': 18} | warning, escalate False | critical, escalate False |
| 110 | P2 | 139 | 92.5 | 37 | 37.2 | {'age_months': None} | stable, escalate False | warning, escalate False |
| 123 | P2 | 138 | 95.8 | 16 | 38.8 | {'age_months': 1} | stable, escalate False | warning, escalate False |
| 137 | P6 | 89 | 90.0 | 27 | 37.3 | {'age_months': 48, 'force_heavy': True} | stable, escalate False | critical, escalate False |
| 139 | P6 | 75 | 96.1 | 38 | 38.9 | {'age_months': 48} | stable, escalate False | critical, escalate False |
| 142 | P2 | 98 | 97.1 | 34 | 39.2 | {'age_months': 18} | stable, escalate False | warning, escalate False |
| 160 | P7 | 142 | 91.0 | 39 | 38.7 | {'age_months': None} | warning, escalate False | critical, escalate False |
| 163 | P2 | 83 | 95.5 | 37 | 37.0 | {'age_months': 18} | stable, escalate False | warning, escalate False |
| 166 | P7 | 110 | nan | 31 | 36.3 | {'age_months': None} | warning, escalate False | critical, escalate False (unassessable) |
| 177 | P7 | 80 | 96.0 | 26 | 37.2 | {'age_months': None} | warning, escalate False | critical, escalate False |
| 190 | P11 | 139 | 82.9 | 40 | 39.0 | {'age_months': 18} | stable, escalate False | warning, escalate True |
| 191 | P3 | 132 | 82.4 | 35 | 39.6 | {'age_months': 6, 'force_heavy': True} | stable, escalate False | warning, escalate True |
| 225 | P9 | 145 | 91.2 | 38 | 38.2 | {'age_months': 48} | stable, escalate False | critical, escalate False |
| 229 | P3 | 116 | 98.1 | 18 | 36.4 | {'age_months': 18} | stable, escalate False | warning, escalate False |
| 236 | P9 | 118 | 97.6 | 36 | 39.1 | {'age_months': 18} | stable, escalate False | critical, escalate False |
| 273 | P4 | 131 | 79.7 | 41 | 39.4 | {'age_months': 48} | warning, escalate False | critical, escalate False |
| 276 | P4 | 94 | 99.2 | 19 | 38.7 | {'age_months': 18} | warning, escalate False | critical, escalate False |
| 282 | P8 | 94 | 90.8 | 21 | 36.5 | {'age_months': 18} | stable, escalate False | warning, escalate True |
| 291 | P10 | 135 | 84.7 | 42 | 39.7 | {'age_months': 1} | stable, escalate False | warning, escalate True |
| 293 | P10 | 105 | 93.8 | 35 | 37.9 | {'age_months': 1} | stable, escalate False | warning, escalate False |
| 295 | P3 | 159 | 80.8 | 46 | 40.4 | {'age_months': 6} | critical, escalate False | critical, escalate True |
| 300 | P0 | 78 | 91.6 | 23 | 38.1 | {'age_months': 48} | warning, escalate False | critical, escalate False |
| 326 | P0 | 89 | 90.6 | 18 | 39.2 | {'age_months': 48, 'force_heavy': True} | stable, escalate False | critical, escalate False |
| 336 | P0 | 97 | 94.4 | 18 | 37.1 | {'age_months': 18} | stable, escalate False | critical, escalate False |
| 344 | P11 | 120 | 90.4 | 23 | 36.5 | {'age_months': 6} | stable, escalate False | critical, escalate False |
| 361 | P7 | 139 | 87.4 | 35 | 40.2 | {'age_months': 6} | stable, escalate False | critical, escalate False |
| 376 | P4 | 98 | 90.2 | 30 | 37.5 | {'age_months': 48, 'force_heavy': True} | stable, escalate False | critical, escalate False |
| 388 | P4 | 70 | 96.2 | 24 | 38.5 | {'age_months': None} | stable, escalate False | critical, escalate False |
| 400 | P7 | 111 | 93.4 | 18 | 36.8 | {'age_months': 6} | stable, escalate False | critical, escalate False |
| 414 | P7 | 78 | 94.6 | 22 | 36.9 | {'age_months': 48} | stable, escalate False | critical, escalate False |
| 417 | P11 | 156 | 80.5 | 55 | 39.8 | {'age_months': 1} | critical, escalate False | critical, escalate True |
| 429 | P6 | 140 | 90.1 | 35 | 38.5 | {'age_months': 48, 'force_heavy': True} | warning, escalate False | critical, escalate False |
| 453 | P3 | 145 | 91.7 | 59 | 40.0 | {'age_months': None} | warning, escalate False | critical, escalate False |
| 459 | P3 | 130 | 93.0 | 38 | 38.8 | {'age_months': 1} | warning, escalate False | critical, escalate False |
| 510 | P10 | 134 | 84.4 | 41 | 39.7 | {'age_months': None} | stable, escalate False | warning, escalate True |
| 516 | P10 | 137 | 90.3 | 31 | 36.5 | {'age_months': 6, 'previous_o2': 'x'} | stable, escalate False | warning, escalate False |
| 564 | P4 | 150 | 91.8 | 52 | 39.2 | {'age_months': 18} | warning, escalate False | critical, escalate False |
| 571 | P10 | 74 | 90.3 | 32 | 38.9 | {'age_months': 18, 'force_heavy': True} | stable, escalate False | warning, escalate True |
