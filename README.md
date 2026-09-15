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

npm run build     # web -> dist/web
npm run verify    # lint + tests + build — same gate CI runs
```

`npm run verify` is the oracle. Green means done.
