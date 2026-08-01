# Applying: remove-dead-callerintent-enum

Small one -- removes a dead enum in sentinel_core.py found while answering
your V12/cassette question, plus a docstring update.

Base: origin/main @ 9cdb759
Branch tip: ddbe04c

```
cd ~/sentinel_os/sentinel_os
git fetch /mnt/chromeos/MyFiles/Downloads/remove-dead-callerintent-enum.bundle remove-dead-callerintent-enum:remove-dead-callerintent-enum
git merge remove-dead-callerintent-enum
git push origin main
```

442 passed, 6 skipped (unchanged). ruff clean, bandit -ll clean.
