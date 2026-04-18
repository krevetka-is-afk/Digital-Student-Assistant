# k6 Scenarios For VM Sizing

These scripts are the executable counterparts of
`docs/load-test-vm-sizing-runbook.md`.

## Prerequisites

- install `k6`
- run from a machine other than the target VM
- point `BASE_URL` to the public staging URL

## Available Scenarios

- `read-heavy.js` for public and lightweight authenticated reads
- `auth-api.js` for token issuance and authenticated API reads
- `write-flow.js` for controlled write pressure with dedicated test users

## Examples

Read-heavy:

```bash
BASE_URL="https://dsa.s3rg.ru" \
k6 run perf/k6/read-heavy.js
```

Auth + API:

```bash
BASE_URL="https://dsa.s3rg.ru" \
AUTH_USERNAME="loadtest@example.com" \
AUTH_PASSWORD="change-me" \
k6 run perf/k6/auth-api.js
```

Write flow:

```bash
BASE_URL="https://dsa.s3rg.ru" \
WRITE_USERNAME="loadtest-customer@example.com" \
WRITE_PASSWORD="change-me" \
k6 run perf/k6/write-flow.js
```

`write-flow.js` expects an account that is allowed to create initiative projects.

## Notes

- use dedicated test accounts;
- keep entity names prefixed with `loadtest-`;
- do not point `write-flow.js` at production unless the target data set is explicitly disposable;
- tune arrival rates only after collecting one stable baseline on the current VM size.
