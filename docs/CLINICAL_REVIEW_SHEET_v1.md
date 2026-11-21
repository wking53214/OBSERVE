# OBSERVE engine re-sync: clinical review sheet (v1)

For the clinical reviewer. Companion to `ENGINE_RESYNC_DISPOSITIONS.md`, which lists the seven readings and keeps their status. Nothing here is approved yet.

## What changed

The root scoring engine was updated to match observe-perceive `d596262`. On the 600-reading test set, 50 readings changed alert or severity. 43 became more cautious and 7 became less cautious. Only the 7 less cautious ones need sign-off. The new engine is already live on main (PR #35).

For each item below, please answer **Accept**, **Reject** or **Change**, with a note.

## 1. Reading 330 (check first)

- Patient P0. SpO2 is missing, so the reading cannot be fully assessed.
- Severity rose from warning to critical, but no alert fired. The patient had a critical alert earlier (reading 247).
- Question: should a patient who dipped to warning and then returns to critical get a new alert?
- Reproduced separately with synthetic readings on 2026-11-20: after a critical alert, a dip to warning and a return to critical inside the cooldown sends no second alert, with or without SpO2. The patient is held at critical the whole time, so the dip is never shown as a drop.

## 2. Readings 148, 353, 481 (repeat critical alerts dropped)

- All three are critical readings with low SpO2 (84.4, 86.2, 88.8) and high heart and breathing rates.
- Each came after an earlier critical alert for the same patient (readings 107, 308, 305). No alert fired this time.
- Question: is one alert per critical episode enough, or should a repeat alert fire after a set time? If so, after how long?

## 3. Reading 585 (repeat warning dropped)

- The SpO2 reading was 250, which is impossible, so the reading cannot be assessed.
- A warning alert had fired 120 seconds earlier. This one is suppressed.
- Question: is a 120-second repeat on an unreadable reading fine to suppress?

## 4. Readings 378 and 398 (critical became stable)

- The patient was critical, then the next reading scored low risk (0.19 and 0.16). The old engine would have kept the patient critical.
- The new engine returns to stable when the reading's own risk is low.
- Question: should a critical patient be allowed to drop straight to stable on one good reading, or should it step down gradually?

## 5. The oxygen case

- A 24-month-old with SpO2 86, temperature 39.1, heart rate 138 and breathing rate 34.
- Old engine: stable, no alert (run 2026-11-16). New engine: **warning with an alert**, with or without normal history (run 2026-11-20).
- Question: is warning the right level, or should it be critical?

## What was verified

The four earlier escalation fixes still hold on the new engine (checked 2026-11-20 with synthetic scenarios, not the original tests):

1. A cooldown does not hide a worsening patient; the alert is labeled a severity increase.
2. A single critical reading after the cooldown alerts at once.
3. A missing or impossible reading does not block the next real critical alert.
4. The oxygen case is no longer stable (see item 5).

Items 2 and 4 above come from the engine's repeat-suppression design. The length of the suppression window was not checked.
