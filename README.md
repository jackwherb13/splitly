# Splitly

Shared house ledger — who owes who, recurring bills split and posted automatically,
unpaid debts chased without anyone having to nag.

`SPEC.md` is the source of truth. `docs/Decisions.md` records why things are the way
they are; `docs/Research.md` holds the sourced external findings the spec leans on.

## Layout

```
web/    Vite + React PWA        (SPEC §C25)
api/    Python — Lambda handlers, ledger core   (SPEC §C27)
docs/   decisions + research
dist/   all build artifacts, gitignored         (SPEC §C37)
```

## One-step build

```
npm install --prefix web
python -m pip install -e "api[dev]"

npm run build     # web -> dist/web, Lambda deps layer -> dist/lambda/layer
```

## Configuring the web app

The app reads three values at build time. None are secrets — the Cognito
client id and the API URL ship inside every bundle by design. They are
generated from Terraform outputs rather than committed, so they cannot drift
from the deployed infrastructure:

```
@"
VITE_API_URL=$(terraform -chdir=infra output -raw api_endpoint)
VITE_COGNITO_CLIENT_ID=$(terraform -chdir=infra output -raw cognito_client_id)
VITE_AWS_REGION=us-east-1
VITE_VAPID_PUBLIC_KEY=$(aws ssm get-parameter --name /splitly/vapid/public_key --query Parameter.Value --output text --profile splitly)
"@ | Out-File -Encoding ascii web/.env
```

Re-run that after any apply that replaces the API or the user pool.
`terraform apply` zips `dist/lambda/layer`, so run `npm run build` before it.
`web/.env.example` lists the keys. Deploying the built app:

```
npm run build
aws s3 sync dist/web "s3://$(terraform -chdir=infra output -raw web_bucket)" --delete --profile splitly
aws cloudfront create-invalidation --distribution-id $(terraform -chdir=infra output -raw web_distribution_id) --paths "/*" --profile splitly
```

## Running the checks

`npm run verify` is the oracle. Green means done.

### Locally, before you push

```
npm run verify    # lint + tests + build — byte-for-byte what CI runs
```

Tighter loops while working:

```
npm run lint      # eslint on web/, ruff on api/
npm run test      # pytest
```

CI installs from a clean slate, so if `verify` passes locally but fails on
GitHub, reinstall first and try again — stale local deps are the usual cause:

```
npm ci --prefix web
python -m pip install -e "api[dev]"
```

### On GitHub

CI runs automatically on every push to `main` and on every pull request.
There is no manual trigger today — to add one, put `workflow_dispatch:`
under `on:` in `.github/workflows/ci.yml`, after which `gh workflow run CI`
and the "Run workflow" button both work.

```
gh run list --limit 5                 # recent runs and their status
gh run watch <run-id> --exit-status   # follow a run, exit 1 if it fails
gh run view --log-failed              # only the failing step's output
gh run rerun <run-id>                 # re-run a flake without an empty commit
```

`gh run watch` needs a run id whenever it is not attached to a terminal, so
to follow the run you just pushed:

```
gh run watch $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status
```

