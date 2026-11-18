## What and why

<!-- One or two sentences. Link the milestone slice from docs/pending.md. -->

## How it was verified

<!-- Commands you ran and what they showed. Say what you could not check. -->

- [ ] `make check`
- [ ] `make test-int`

## Checklist

- [ ] A new tenant table ships with its `tenant_isolation` policy and an isolation test
- [ ] Endpoints declare a permission; another tenant's row returns 404
- [ ] No secrets, account ids or personal data in the diff
- [ ] `docs/progress.md` and `docs/pending.md` updated; a decision got an ADR, a surprise got a line in `docs/what-broke.md`
