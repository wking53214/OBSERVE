# Engine re-sync: disposition of the seven less-cautious readings (2026-11-19)

Companion to `ENGINE_RESYNC_DIFFERENCES.md`. For each reading where the new engine (observe-perceive `d596262`) is less cautious than the old one: what changed, the likely reason, and the decision status.

**Every disposition below is PENDING clinical review.** Nothing here is approved. The "likely reason" column is inferred from the recorded readings, not confirmed in the engine code. The new engine is already merged on main (PR #35), so these seven behaviors are live today.

Common pattern: in the new engine each of these patients had already been escalated at an earlier reading, and the reading in question is at the same severity. That fits the upstream change that suppresses a repeat escalation at the same severity (a higher severity still escalates). The length of that suppression window was not checked.

| Reading | Patient | What changed | Likely reason (inferred) | Disposition |
|---|---|---|---|---|
| 148 | P6 | Critical, alert dropped (True to False). SpO2 84.4, HR 144, RR 38, temp 40.0, age 1 month. | Repeat at same severity after an earlier critical alert (reading 107). | PENDING clinical review |
| 330 | P0 | Warning with alert became critical with no alert. Unassessable (SpO2 missing). Risk 0.50 to 0.75. | Severity went up but no alert, although the patient had a critical alert at reading 247. A severity increase is supposed to escalate, so the reviewer should check this one first. | PENDING clinical review |
| 353 | P11 | Critical, alert dropped. SpO2 86.2, HR 146, RR 36, age missing. | Repeat at same severity after an earlier critical alert (reading 308). | PENDING clinical review |
| 378 | P11 | Critical became stable. Risk 0.19, unchanged. | Old engine kept the patient critical after reading 353; new engine returns to stable when the reading's own risk is low. | PENDING clinical review |
| 398 | P11 | Critical became stable. Risk 0.16, unchanged. | Same as 378. | PENDING clinical review |
| 481 | P7 | Critical, alert dropped. SpO2 88.8, HR 174, RR 43, age 18 months. Risk 1.0. | Repeat at same severity after an earlier critical alert (reading 305). | PENDING clinical review |
| 585 | P10 | Warning, alert dropped. Unassessable (SpO2 250, impossible). | Repeat at same severity after a warning alert at reading 571, 120 seconds earlier. | PENDING clinical review |

## What the tests pin

`test_engine_resync_differential.py::TheSevenLessCautiousReadings` pins the new engine's exact output for these seven readings. It does not say the output is right. If the engine changes these, the test fails and the change has to be decided on purpose. No test asserts that these readings must escalate, because that would be a clinical call this repo has not been given.
