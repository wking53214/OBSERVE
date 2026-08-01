Two independent patches against origin/main (5fb20b3), verified to apply
cleanly with `git apply --check` against a fresh checkout.

Apply + commit each on its own, in order:

  git apply 01-AUDIT_PLAYBOOK.patch
  git add sentinel_os/AUDIT_PLAYBOOK.md
  git commit -F 01-AUDIT_PLAYBOOK.commitmsg

  git apply 02-COMPLIANCE.patch
  git add sentinel_os/COMPLIANCE.md
  git commit -F 02-COMPLIANCE.commitmsg

Not pushed anywhere -- these only exist in this sandbox and the files
below. Nothing has touched origin/main.
